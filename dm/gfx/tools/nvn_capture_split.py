#!/usr/bin/env python3
"""Build a dmsh package from complete local NVN ProgramSetShaders captures.

The capture directory is private game-derived data and must stay outside the
repository.  Output package/map/facts contain shader bytes too and likewise
belong in a local build workspace, never in source control.

Usage: nvn_capture_split.py <capture-dir> <package-dir> <shader-map.tsv>
                            <shader-facts.tsv> <shader-pairs.tsv>
       nvn_capture_split.py --self-test
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile

os.environ.setdefault('DM_GAME', '0100000000010000')
sys.path.insert(0, os.path.dirname(__file__))
import shader_split as split

CAPTURE_NAME = re.compile(r'^(\d+)-([0-9a-fA-F]{16})-(\d+)$')


def read_capture(meta_path):
    meta = json.loads(meta_path.read_text())
    stem = meta_path.name[:-10]
    match = CAPTURE_NAME.match(stem)
    if not match or not meta.get('dataComplete') or not meta.get('controlComplete'):
        return None
    data_path = meta_path.with_name(stem + '.prefix.bin')
    control_path = meta_path.with_name(stem + '.control.bin')
    if not data_path.exists() or not control_path.exists():
        return None
    control = control_path.read_bytes()
    data = data_path.read_bytes()
    if len(control) != 0x880 or len(data) != meta.get('dataBytes'):
        return None
    ncode = struct.unpack_from('<I', control, 0x704)[0]
    if not ncode or ncode > len(data):
        return None
    code = data[:ncode]
    if meta.get('dataHeaderBytes') == 0:
        stage = 'cs'
    elif code[:4] == split.GFX_MAGIC:
        stage = split.sph_stage(code)
    else:
        return None
    if not stage or split.check(stem, stage, control, code):
        return None
    key = split.skey(control, code)
    return {
        'key': key,
        'stage': stage,
        'control': control,
        'code': code,
        'source': f'/nvn_capture#UE{stem}',
        'program': (match.group(1), match.group(2)),
    }


def collect(capture_dir):
    shaders = {}
    programs = collections.defaultdict(dict)
    rejected = 0
    for meta_path in sorted(Path(capture_dir).glob('*.meta.json')):
        shader = read_capture(meta_path)
        if not shader:
            rejected += 1
            continue
        key = shader['key']
        old = shaders.get(key)
        if old and not split.same_shader(old['control_code'], (shader['control'], shader['code'])):
            raise ValueError(f'key collision {key}: {old["source"]} / {shader["source"]}')
        if not old:
            shader['control_code'] = (shader['control'], shader['code'])
            shaders[key] = shader
        programs[shader['program']][shader['stage']] = key
    observed = {(stages['vs'], stages['ps']) for stages in programs.values()
                if 'vs' in stages and 'ps' in stages}
    separable, _ = split.separable_pairs({
        key: (shader['source'], shader['stage'], shader['control'], shader['code'])
        for key, shader in shaders.items()
    })
    return shaders, observed | separable, rejected


def write_outputs(shaders, pairs, package_dir, map_path, facts_path, pairs_path):
    package_dir = Path(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    for old in package_dir.glob('*.bin'):
        old.unlink()
    records = collections.defaultdict(list)
    rows = []
    facts = {}
    for key, shader in sorted(shaders.items(), key=lambda item: (item[1]['stage'], item[0])):
        stage = shader['stage']
        name = f'{stage}_capture.bin'
        record = bytearray(b'BTCDBTCD' + bytes(0x30))
        struct.pack_into('<2I', record, 0x28, len(shader['control']), len(shader['code']))
        record += shader['code'] + shader['control']
        rows.append((name, len(records[name]), split.STAGE_NAME[stage], key, shader['source']))
        records[name].append(bytes(record))
        if stage == 'cs':
            local = list(struct.unpack_from('<3I', shader['control'], 0x748))
            shared = struct.unpack_from('<I', shader['control'], 0x754)[0]
            if not all(local):
                raise ValueError(f'compute shader {key} has zero local size')
            facts[key] = {'local': local, 'shared': (shared + 15) // 16 * 16}
    for name, items in records.items():
        (package_dir / name).write_bytes(b''.join(items))
    with open(map_path, 'w') as out:
        out.write('# Local runtime NVN capture -> dmsh package; game-derived binaries remain outside the repository\n')
        out.write('package\tindex\tstage\tdm_ctl_sha16\tsource\n')
        for row in rows:
            out.write('\t'.join(map(str, row)) + '\n')
    with open(facts_path, 'w') as out:
        out.write('# Compute facts observed in runtime NVN control sections\n')
        for key in sorted(facts):
            out.write(key + '\t' + json.dumps(facts[key], sort_keys=True, separators=(',', ':')) + '\n')
    with open(pairs_path, 'w') as out:
        out.write('# vertex key\tpixel key observed in one NVN program\n')
        for vertex, pixel in sorted(pairs):
            out.write(f'{vertex}\t{pixel}\n')


def self_test():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        control = bytearray(0x880)
        control[:4] = split.CTL_MAGIC
        struct.pack_into('<I', control, 0x20, len(control))
        struct.pack_into('<I', control, 0x704, 0x80)
        code = bytearray(0x80)
        code[:4] = split.GFX_MAGIC
        struct.pack_into('<I', code, 0x30, 1 << 10)
        stem = '1-0000000000000001-0'
        (root / (stem + '.control.bin')).write_bytes(control)
        (root / (stem + '.prefix.bin')).write_bytes(code)
        (root / (stem + '.meta.json')).write_text(json.dumps({
            'dataComplete': True, 'controlComplete': True,
            'dataBytes': len(code), 'dataHeaderBytes': 48,
        }))
        shaders, pairs, rejected = collect(root)
        assert len(shaders) == 1 and not pairs and not rejected
        key = next(iter(shaders))
        assert key == hashlib.sha256(control + code).hexdigest()[:16]
    print('PASS: runtime NVN capture -> dmsh shader key')


def main():
    if sys.argv[1:] == ['--self-test']:
        self_test()
        return
    if len(sys.argv) != 6:
        raise SystemExit(__doc__)
    shaders, pairs, rejected = collect(sys.argv[1])
    if not shaders:
        raise SystemExit('[RED] no complete valid NVN shader captures')
    write_outputs(shaders, pairs, *sys.argv[2:])
    count = collections.Counter(shader['stage'] for shader in shaders.values())
    print(f'shaders: {len(shaders)} ({dict(sorted(count.items()))}); pairs: {len(pairs)}; rejected captures: {rejected}')


if __name__ == '__main__':
    main()
