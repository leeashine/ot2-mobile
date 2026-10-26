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


def compact_uexp_record(stage=b'SV', flags=b'\0\1'):
    code = bytearray(0x80)
    code[:4] = shader_split.GFX_MAGIC
    stage_type = {b'SV': 1, b'SP': 5}[stage]
    struct.pack_into('<I', code, 0x30, stage_type << 10)
    control = bytearray(0x880)
    control[:4] = shader_split.CTL_MAGIC
    struct.pack_into('<I', control, 0x20, len(control))
    struct.pack_into('<I', control, 0x704, len(code))
    payload = bytes(code) + struct.pack('<I', len(code)) + bytes(control) + b'!!NVfp5.0\nEND'
    # The block begins at record +1. Its first token is the 'S' of LSLG.
    # The two flag bytes double as a one-byte-offset LZ4 match.
    return b'LSLG' + stage + flags + b'\0' + lz4_literal_block(payload)


def test_compact_uexp():
    record = compact_uexp_record()
    found, stats = ot2_uexp_static.extract_compact_lslg_shaders(record, '/compact.uexp')
    assert len(found) == 1
    where, stage, control, code = found[0]
    assert where.endswith('#UEXPLZ4@0') and stage == 'vs'
    assert control[:4] == shader_split.CTL_MAGIC and code[:4] == shader_split.GFX_MAGIC
    assert struct.unpack_from('<I', control, 0x704)[0] == len(code)
    assert stats['flag01'] == 1 and stats['decoded'] == 1 and stats['rejected'] == 0
    adjacent, adjacent_stats = ot2_uexp_static.extract_compact_lslg_shaders(
        record + b'LSLGSP\0\0' + bytes(32), '/adjacent.uexp')
    assert len(adjacent) == 1 and adjacent_stats['records'] == 2
    assert adjacent_stats['decoded'] == 1 and adjacent_stats['flag00'] == 1

    skipped, skip_stats = ot2_uexp_static.extract_compact_lslg_shaders(
        b'LSLGSP\0\0' + bytes(32), '/flag00.uexp')
    assert not skipped and skip_stats['flag00'] == 1
    failed, fail_stats = ot2_uexp_static.extract_compact_lslg_shaders(
        b'LSLGSV\0\1', '/truncated.uexp')
    assert not failed and fail_stats['rejected'] == 1
    assert fail_stats['decode_truncated_offset'] == 1


def test_runtime_merge():
    vertex, _ = ot2_uexp_static.extract_compact_lslg_shaders(
        compact_uexp_record(b'SV'), '/static-vs.uexp')
    pixel, _ = ot2_uexp_static.extract_compact_lslg_shaders(
        compact_uexp_record(b'SP'), '/static-ps.uexp')
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
    fake = FakePak([name], {name: compact_uexp_record()})
    path = 'synthetic.pak'
    shader_split._PAKS.pop(path, None)
    try:
        with mock.patch.object(shader_split.uepak, 'Pak', return_value=fake):
            found = []
            shader_split.ue_inline_pak_shaders(path, 'synthetic.pak', [name], found)
    finally:
        shader_split._PAKS.pop(path, None)
    assert len(found) == 1 and found[0][1] == 'vs'
    assert found[0][0].endswith('#UEXPLZ4@0')

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
