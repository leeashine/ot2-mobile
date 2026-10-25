#!/usr/bin/env python3
"""Synthetic regression coverage for Unreal inline shaders in version-11 paks."""
import os
import struct
import sys
import zlib

os.environ.setdefault('DM_GAME', '0100000000010000')
sys.path.insert(0, os.path.dirname(__file__))
import shader_split


class FakePak:
    version = 11

    def __init__(self, names):
        self.files = {name: i for i, name in enumerate(names)}


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


if __name__ == '__main__':
    main()
