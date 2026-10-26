#!/usr/bin/env python3
"""Synthetic regression coverage for Unreal inline shaders in version-11 paks."""
import os
import struct
import sys
import zlib

os.environ.setdefault('DM_GAME', '0100000000010000')
sys.path.insert(0, os.path.dirname(__file__))
import json
import tempfile
from pathlib import Path
from unittest import mock

import shader_split
import ot2_uexp_static


def lz4_literal_block(data):
    size = len(data)
    encoded = bytearray([0xf0])
    remaining = size - 15
    while remaining >= 255:
        encoded.append(255)
        remaining -= 255
    encoded.append(remaining)
    encoded.extend(data)
    return bytes(encoded)


def lz4_block_at_lslg(payload, delta):
    if delta == 1:
        assert payload[8:12] == bytes(4)
        return b'\x80' + payload[:8] + b'\x01\x00' + lz4_literal_block(payload[12:])
    if delta == 2:
        assert payload[15:19] == bytes(4)
        return b'\xf0\x00' + payload[:15] + b'\x01\x00' + lz4_literal_block(payload[19:])
    raise ValueError('LSLG offset must be one or two bytes')


def compact_uexp_record(stage=b'SV', lslg_delta=2):
    code = bytearray(0x80)
    code[:4] = shader_split.GFX_MAGIC
    stage_type = {b'SV': 1, b'SP': 5}[stage]
    struct.pack_into('<I', code, 0x30, stage_type << 10)
    control = bytearray(0x880)
    control[:4] = shader_split.CTL_MAGIC
    struct.pack_into('<I', control, 0x20, len(control))
    struct.pack_into('<I', control, 0x704, len(code))
    prefix = b'LSLG' + stage + bytes(2)
    padding = bytes(4) if lslg_delta == 1 else bytes(7) + bytes(4)
    payload = (prefix + padding + bytes(code) + struct.pack('<I', len(code))
               + bytes(control) + b'!!NVfp5.0\nEND')
    block = lz4_block_at_lslg(payload, lslg_delta)
    return struct.pack('<I', len(block)) + block


def test_compact_uexp():
    for delta in (1, 2):
        record = compact_uexp_record(lslg_delta=delta)
        found, stats = ot2_uexp_static.extract_compact_lslg_shaders(
            record, f'/compact-minus-{delta}.uexp')
        assert len(found) == 1
        where, stage, control, code = found[0]
        assert where.endswith('#UEXPLZ4@4') and stage == 'vs'
        assert control[:4] == shader_split.CTL_MAGIC and code[:4] == shader_split.GFX_MAGIC
        assert struct.unpack_from('<I', control, 0x704)[0] == len(code)
        assert stats['records'] == 1 and stats['decoded'] == 1 and stats['rejected'] == 0
        assert stats[f'candidate_success_start_minus_{delta}'] == 1

    joined = (compact_uexp_record(lslg_delta=1) + bytes(7)
              + compact_uexp_record(stage=b'SP', lslg_delta=2))
    found, stats = ot2_uexp_static.extract_compact_lslg_shaders(joined, '/adjacent.uexp')
    assert len(found) == 2 and stats['records'] == 2 and stats['decoded'] == 2
    assert {shader[1] for shader in found} == {'vs', 'ps'}

    truncated = bytearray(compact_uexp_record(lslg_delta=2))
    struct.pack_into('<I', truncated, 0, struct.unpack_from('<I', truncated, 0)[0] - 1)
    found, stats = ot2_uexp_static.extract_compact_lslg_shaders(
        bytes(truncated), '/wrong-length.uexp')
    assert not found and stats['records'] == 1 and stats['rejected'] == 1
    assert stats['candidate_failure_lz4_invalid_block'] >= 1
    assert sum(value for key, value in stats.items()
               if key.startswith('rejected_reason_') and '_start_minus_' not in key) == 1

    fake = b'LSLGSP' + bytes(32)
    found, stats = ot2_uexp_static.extract_compact_lslg_shaders(fake, '/not-a-block.uexp')
    assert not found and stats['records'] == 1 and stats['rejected'] == 1


def test_runtime_merge():
    vertex, _ = ot2_uexp_static.extract_compact_lslg_shaders(
        compact_uexp_record(b'SV', lslg_delta=1), '/static-vs.uexp')
    pixel, _ = ot2_uexp_static.extract_compact_lslg_shaders(
        compact_uexp_record(b'SP', lslg_delta=2), '/static-ps.uexp')
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for stem, shader in (
            ('7-0000000000000007-0', vertex[0]),
            ('7-0000000000000007-1', pixel[0]),
        ):
            _, _, control, code = shader
            (root / (stem + '.control.bin')).write_bytes(control)
            (root / (stem + '.prefix.bin')).write_bytes(code)
            (root / (stem + '.meta.json')).write_text(json.dumps({
                'dataComplete': True, 'controlComplete': True,
                'dataBytes': len(code), 'dataHeaderBytes': 48, 'controlBytes': 0x880,
            }))
        vertex_key = shader_split.skey(vertex[0][2], vertex[0][3])
        pixel_key = shader_split.skey(pixel[0][2], pixel[0][3])
        merged = {vertex_key: vertex[0]}
        pairs, accepted, rejected, added = shader_split.merge_nvn_captures(merged, [root])
        assert len(merged) == 2 and accepted == 2 and rejected == 0 and added == 1
        assert pairs == {(vertex_key, pixel_key)}


def test_compact_global_shader_cache():
    name = 'Engine/GlobalShaderCache-SF_GLSL_SWITCH.bin'
    fake = FakePak([name], {name: compact_uexp_record(lslg_delta=1)})
    path = 'synthetic.pak'
    shader_split._PAKS.pop(path, None)
    try:
        with mock.patch.object(shader_split.uepak, 'Pak', return_value=fake):
            found = []
            shader_split.ue_inline_pak_shaders(path, 'synthetic.pak', [name], found)
    finally:
        shader_split._PAKS.pop(path, None)
    assert len(found) == 1 and found[0][1] == 'vs'
    assert found[0][0].endswith('#UEXPLZ4@4')


class FakePak:
    version = 11
    mount = ''

    def __init__(self, names, contents=None):
        self.files = {name: i for i, name in enumerate(names)}
        self.contents = contents or {}

    def entry(self, name):
        return {'method': ''}

    def read(self, name, decode=None):
        return self.contents[name]

def shader_record():
    code = bytearray(0x80)
    code[:4] = shader_split.GFX_MAGIC
    struct.pack_into('<I', code, 0x30, 1 << 10)  # vertex stage
    ctl = bytearray(0x880)
    ctl[:4] = shader_split.CTL_MAGIC
    struct.pack_into('<I', ctl, 0x20, len(ctl))
    struct.pack_into('<I', ctl, 0x704, len(code))
    return b'LSLGSV\0\0' + struct.pack('<I', len(code)) + code + struct.pack('<I', len(ctl)) + ctl


def main():
    inline = FakePak([
        'Engine/GlobalShaderCache-SF_GLSL_SWITCH.bin',
        'Majesty/Content/Material.uexp',
        'Majesty/Content/Texture.ubulk',
    ])
    assert shader_split.ue_inline_names(inline) == (
        'Engine/GlobalShaderCache-SF_GLSL_SWITCH.bin',
        'Majesty/Content/Material.uexp',
    )
    archive = FakePak([
        'Engine/GlobalShaderCache-SF_GLSL_SWITCH.bin',
        'Majesty/Content/Material.uexp',
        'ShaderArchive-Majesty.ushaderbytecode',
    ])
    assert shader_split.ue_inline_names(archive) == ()

    record = shader_record()
    compressed = zlib.compress(record)
    outer = b'prefix' + struct.pack('<I', len(compressed)) + compressed + b'suffix'
    found = []
    shader_split.ue_inline_shaders(outer, '/synthetic.uexp', found)
    assert len(found) == 1
    where, stage, ctl, code = found[0]
    assert where.endswith('#UEa') and stage == 'vs'
    assert ctl[:4] == shader_split.CTL_MAGIC and code[:4] == shader_split.GFX_MAGIC
    print('PASS: version-11 inline selection and zlib LSLG extraction')
    test_compact_uexp()
    test_runtime_merge()
    print('PASS: compact UEXP LZ4 extraction and runtime/static capture merge')
    test_compact_global_shader_cache()
    print('PASS: compact GSC records use the same strict LSLG validation')


if __name__ == '__main__':
    main()
