#!/usr/bin/env python3
"""Recover validated NVN shaders from complete UE4.27 LZ4 blocks in cooked paks."""
from collections import Counter
import ctypes
import ctypes.util
import struct

RECORD_MAGIC = b'LSLG'
GFX_MAGIC = bytes.fromhex('78563412')
CS_MAGIC = bytes.fromhex('79563412')
CTL_MAGIC = bytes.fromhex('34127698')
CONTROL_BYTES = 0x880
MAX_DECODED_BYTES = 16 * 1024 * 1024
MAX_LZ4_INPUT = (1 << 31) - 1
_LZ4 = None


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


def _lz4_output_size(src):
    """Validate raw LZ4 block bounds and calculate its exact output capacity."""
    if not src:
        return None, 'empty_block'
    size = 0
    pos = 0
    while pos < len(src):
        token = src[pos]
        pos += 1
        literals, pos = _length(src, pos, token >> 4)
        if literals is None:
            return None, 'truncated_literal_length'
        if pos + literals > len(src):
            return None, 'truncated_literals'
        size += literals
        pos += literals
        if size > MAX_DECODED_BYTES:
            return None, 'decoded_size_limit'
        if pos == len(src):
            return size, None
        if pos + 2 > len(src):
            return None, 'truncated_offset'
        offset = src[pos] | (src[pos + 1] << 8)
        pos += 2
        if offset == 0 or offset > size:
            return None, 'invalid_offset'
        match, pos = _length(src, pos, token & 0x0f)
        if match is None:
            return None, 'truncated_match_length'
        size += match + 4
        if size > MAX_DECODED_BYTES:
            return None, 'decoded_size_limit'
    return size, None


def _lz4_decompress_safe(src, output_size):
    """Decode the exact compressed span with the platform's LZ4_decompress_safe."""
    global _LZ4
    if _LZ4 is None:
        library_name = ctypes.util.find_library('lz4')
        if not library_name:
            raise RuntimeError('liblz4 is required to decode UE inline LZ4 blocks')
        library = ctypes.CDLL(library_name)
        function = library.LZ4_decompress_safe
        function.argtypes = (ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
        function.restype = ctypes.c_int
        _LZ4 = (library, function)
    if not 0 < output_size <= MAX_DECODED_BYTES or len(src) > MAX_LZ4_INPUT:
        return None, 'invalid_output_size'
    destination = ctypes.create_string_buffer(output_size)
    written = _LZ4[1](src, destination, len(src), output_size)
    if written < 0:
        return None, 'invalid_lz4_block'
    if written != output_size:
        return None, 'lz4_output_size_mismatch'
    return destination.raw[:written], None


def _shader_from_decoded(decoded, label, block_start, split):
    if decoded[:4] != RECORD_MAGIC:
        return None, 'output_not_lslg'
    stage_tag = decoded[4:6].decode('latin1')
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
                        return (f'{label}#UEXPLZ4@{block_start:x}', stage, control, code), None
        control_at = decoded.find(CTL_MAGIC, control_at + len(CTL_MAGIC))
    if not saw_control:
        return None, 'missing_control'
    return None, 'invalid_code_length' if bad_length else 'invalid_control_or_stage'


def extract_compact_lslg_shaders(data, label):
    """Scan source bytes for LSLG and decode the exact preceding u32-sized LZ4 block."""
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
    for lslg_offset in starts:
        candidates = []
        candidate_failures = []
        for delta in (1, 2):
            block_start = lslg_offset - delta
            reason = None
            if block_start < 4:
                reason = 'missing_length_header'
            else:
                compressed_size = struct.unpack_from('<I', data, block_start - 4)[0]
                if (not compressed_size or compressed_size > MAX_LZ4_INPUT
                        or compressed_size > len(data) - block_start):
                    reason = 'invalid_compressed_length'
                else:
                    compressed = data[block_start:block_start + compressed_size]
                    output_size, detail = _lz4_output_size(compressed)
                    if detail:
                        reason = 'decoded_size_limit' if detail == 'decoded_size_limit' else 'lz4_invalid_block'
                        if reason == 'lz4_invalid_block':
                            stats[f'candidate_lz4_detail_{detail}'] += 1
                    elif output_size < len(RECORD_MAGIC):
                        reason = 'invalid_output_size'
                    else:
                        decoded, detail = _lz4_decompress_safe(compressed, output_size)
                        if detail:
                            reason = detail
                        elif decoded[:4] != RECORD_MAGIC:
                            reason = 'output_not_lslg'
                        else:
                            shader, detail = _shader_from_decoded(
                                decoded, label, block_start, split)
                            if detail:
                                reason = f'shader_{detail}'
                            else:
                                candidates.append((shader, delta))
            if reason:
                stats[f'candidate_failure_{reason}'] += 1
                candidate_failures.append(reason)
            else:
                stats[f'candidate_success_start_minus_{delta}'] += 1

        if len(candidates) == 1:
            shader, delta = candidates[0]
            shaders.append(shader)
            stats['decoded'] += 1
            stats[f'recovered_start_minus_{delta}'] += 1
        elif len(candidates) > 1:
            stats['rejected'] += 1
            stats['ambiguous'] += 1
        else:
            stats['rejected'] += 1
            if len(set(candidate_failures)) == 1:
                stats[f'rejected_reason_{candidate_failures[0]}'] += 1
            else:
                stats['rejected_reason_mixed'] += 1
                for delta, reason in zip((1, 2), candidate_failures):
                    stats[f'rejected_reason_start_minus_{delta}_{reason}'] += 1
    for key in ('decoded', 'rejected', 'ambiguous'):
        stats.setdefault(key, 0)
    return shaders, dict(stats)
