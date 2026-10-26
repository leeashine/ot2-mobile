#!/usr/bin/env python3
"""Recover NVN shaders from UE 4.27 compact LSLG records in cooked .uexp files.

The 00 01 record form is one dictionary-free LZ4 block beginning at record+1.
Records with 00 00 flags need external history and are deliberately skipped.
"""
from collections import Counter
import struct

RECORD_MAGIC = b'LSLG'
FLAG_LZ4 = b'\x00\x01'
FLAG_EXTERNAL_HISTORY = b'\x00\x00'
GFX_MAGIC = bytes.fromhex('78563412')
CS_MAGIC = bytes.fromhex('79563412')
CTL_MAGIC = bytes.fromhex('34127698')
CONTROL_BYTES = 0x880
MAX_DECODED_BYTES = 16 * 1024 * 1024


def _length(src, pos, base):
    length = base
    if base == 15:
        while True:
            if pos >= len(src):
                return None, pos
            value = src[pos]
            pos += 1
            length += value
            if value != 255:
                break
    return length, pos


def decode_lz4_block(src):
    """Decode one raw LZ4 block without a dictionary.

    Returns (output, consumed, reason). A partial output is retained on malformed
    tails so the caller can accept only when the complete code and control regions
    were already recovered and validated.
    """
    out = bytearray()
    pos = 0
    while pos < len(src):
        token = src[pos]
        pos += 1
        literals, pos = _length(src, pos, token >> 4)
        if literals is None or pos + literals > len(src):
            return bytes(out), pos, 'truncated_literals'
        if len(out) + literals > MAX_DECODED_BYTES:
            return bytes(out), pos, 'decoded_size_limit'
        out.extend(src[pos:pos + literals])
        pos += literals
        if pos == len(src):
            return bytes(out), pos, 'end'
        if pos + 2 > len(src):
            return bytes(out), pos, 'truncated_offset'
        offset = src[pos] | (src[pos + 1] << 8)
        pos += 2
        if offset == 0 or offset > len(out):
            return bytes(out), pos, 'invalid_offset'
        match, pos = _length(src, pos, token & 0x0f)
        if match is None:
            return bytes(out), pos, 'truncated_match_length'
        match += 4
        if len(out) + match > MAX_DECODED_BYTES:
            return bytes(out), pos, 'decoded_size_limit'
        for _ in range(match):
            out.append(out[-offset])
    return bytes(out), pos, 'end'


def _shader_from_decoded(decoded, stage_tag, label, record_offset, split):
    stage = split.UE_TAG.get(stage_tag)
    if not stage:
        return None, 'unknown_stage'
    code_magic = split.CS_MAGIC if stage == 'cs' else split.GFX_MAGIC
    code_at = decoded.find(code_magic)
    if code_at < 0:
        return None, 'missing_code_magic'
    control_at = decoded.find(CTL_MAGIC, code_at + 0x30)
    saw_control = False
    bad_length = False
    while control_at >= 0:
        if control_at + CONTROL_BYTES <= len(decoded):
            saw_control = True
            control = decoded[control_at:control_at + CONTROL_BYTES]
            code_bytes = struct.unpack_from('<I', control, 0x704)[0]
            if code_bytes < 4 or code_at + code_bytes > control_at:
                bad_length = True
            else:
                code = decoded[code_at:code_at + code_bytes]
                if code[:4] in (GFX_MAGIC, CS_MAGIC):
                    why = split.check(label, stage, control, code)
                    if not why:
                        return (f'{label}#UEXPLZ4@{record_offset:x}', stage, control, code), None
        control_at = decoded.find(CTL_MAGIC, control_at + len(CTL_MAGIC))
    if not saw_control:
        return None, 'missing_control'
    return None, 'invalid_code_length' if bad_length else 'invalid_control_or_stage'


def extract_compact_lslg_shaders(data, label):
    """Return validated compact Unreal LSLG shader records and scan counts."""
    import shader_split as split

    starts = []
    offset = 0
    while True:
        offset = data.find(RECORD_MAGIC, offset)
        if offset < 0:
            break
        starts.append(offset)
        offset += len(RECORD_MAGIC)

    stats = Counter(records=len(starts))
    shaders = []
    for index, start in enumerate(starts):
        if start + 8 > len(data):
            stats['truncated_headers'] += 1
            continue
        flags = data[start + 6:start + 8]
        if flags == FLAG_EXTERNAL_HISTORY:
            stats['flag00'] += 1
            continue
        if flags != FLAG_LZ4:
            stats['other_flags'] += 1
            continue

        stats['flag01'] += 1
        end = starts[index + 1] if index + 1 < len(starts) else len(data)
        # The verified record reader includes the next eight-byte LSLG header as
        # the LZ4 boundary tail; decoding stops at its invalid back-reference.
        compressed = data[start + 1:min(len(data), end + 8)]
        decoded, _, stop_reason = decode_lz4_block(compressed)
        stats[f'decode_{stop_reason}'] += 1
        shader, error = _shader_from_decoded(
            decoded, data[start + 4:start + 6].decode('latin1'), label, start, split)
        if error:
            stats['rejected'] += 1
            stats[error] += 1
            continue
        shaders.append(shader)
        stats['decoded'] += 1
        if stop_reason != 'end':
            stats['valid_with_trailing_boundary'] += 1
            stats[f'trailing_{stop_reason}'] += 1
    for key in ('flag00', 'flag01', 'other_flags', 'truncated_headers', 'decoded', 'rejected'):
        stats.setdefault(key, 0)
    return shaders, dict(stats)
