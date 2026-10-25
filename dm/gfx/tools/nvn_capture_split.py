#!/usr/bin/env python3
"""Build a dmsh package from complete local NVN ProgramSetShaders captures.

The capture directory is private game-derived data and must stay outside the
repository.  Output package/map/facts contain shader bytes too and likewise
belong in a local build workspace, never in source control.

Usage: nvn_capture_split.py <capture-dir> <package-dir> <shader-map.tsv>
                            <shader-facts.tsv> <shader-pairs.tsv>
       nvn_capture_split.py --dedupe <capture-dir>
       nvn_capture_split.py --self-test
"""
import collections
import hashlib
import json
import os
import shutil
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


PAIR_SNAPSHOT = '.nvn_capture_pairs.tsv'


def collect(capture_dir, include_stems=None, occurrences=None, extra_pairs=()):
    capture_dir = Path(capture_dir)
    shaders = {}
    programs = collections.defaultdict(dict)
    rejected = 0
    for meta_path in sorted(capture_dir.glob('*.meta.json')):
        stem = meta_path.name[:-10]
        if include_stems is not None and stem not in include_stems:
            continue
        shader = read_capture(meta_path)
        if not shader:
            rejected += 1
            continue
        key = shader['key']
        if occurrences is not None:
            occurrences.setdefault(key, []).append(stem)
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
    pairs = observed | separable | set(extra_pairs)
    pair_path = capture_dir / PAIR_SNAPSHOT
    if pair_path.is_file():
        for line in pair_path.read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            pair = line.split('\t')
            if len(pair) != 2 or not all(re.fullmatch(r'[0-9a-f]{16}', key) for key in pair):
                raise ValueError(f'invalid preserved NVN pair row in {pair_path}: {line!r}')
            pairs.add(tuple(pair))
    for vertex, pixel in pairs:
        if vertex not in shaders or pixel not in shaders:
            raise ValueError(f'NVN pair references absent shader keys: {vertex} / {pixel}')
        if shaders[vertex]['stage'] != 'vs' or shaders[pixel]['stage'] != 'ps':
            raise ValueError(f'NVN pair has invalid stages: {vertex} / {pixel}')
    return shaders, pairs, rejected


def deduplicate(capture_dir):
    directory = Path(capture_dir)
    occurrences = {}
    before_shaders, before_pairs, rejected = collect(directory, occurrences=occurrences)
    keep = {min(stems) for stems in occurrences.values()}
    duplicates = {stem for stems in occurrences.values() for stem in stems if stem not in keep}
    if not duplicates:
        after_shaders, after_pairs, _ = collect(directory)
        if set(after_shaders) != set(before_shaders) or after_pairs != before_pairs:
            raise ValueError('NVN collect changed shader or pair sets without deduplication')
        return len(occurrences), len(keep), 0, len(before_shaders), len(before_pairs), rejected

    stage = Path(tempfile.mkdtemp(prefix=f'.{directory.name}.dedupe-', dir=directory.parent))
    backup = stage.with_name(stage.name + '.original')
    remove_names = {stem + suffix for stem in duplicates for suffix in ('.meta.json', '.prefix.bin', '.control.bin')}
    try:
        for source in directory.iterdir():
            if source.name in remove_names:
                continue
            if source.is_symlink() or not source.is_file():
                raise ValueError(f'unexpected non-file in NVN capture directory: {source}')
            os.link(source, stage / source.name)
        staged_shaders, staged_pairs, _ = collect(stage)
        if set(staged_shaders) != set(before_shaders) or staged_pairs != before_pairs:
            snapshot = stage / (PAIR_SNAPSHOT + '.tmp')
            with snapshot.open('w') as out:
                out.write('# Pair associations preserved across per-key capture deduplication\n')
                for vertex, pixel in sorted(before_pairs):
                    out.write(f'{vertex}\t{pixel}\n')
            os.replace(snapshot, stage / PAIR_SNAPSHOT)
            staged_shaders, staged_pairs, _ = collect(stage)
        if set(staged_shaders) != set(before_shaders) or staged_pairs != before_pairs:
            raise ValueError('per-key deduplication cannot preserve nvn_capture_split.collect shader and pair sets')

        directory.rename(backup)
        try:
            stage.rename(directory)
            after_shaders, after_pairs, _ = collect(directory)
            if set(after_shaders) != set(before_shaders) or after_pairs != before_pairs:
                raise ValueError('post-dedup collect differs from the original shader or pair sets')
        except BaseException:
            if directory.exists():
                shutil.rmtree(directory)
            backup.rename(directory)
            raise
        shutil.rmtree(backup)
        return sum(map(len, occurrences.values())), len(keep), len(duplicates), len(before_shaders), len(before_pairs), rejected
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        if backup.exists() and not directory.exists():
            backup.rename(directory)
        raise


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
    Path(str(map_path) + '.conflicts.tsv').write_text('')


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
    if len(sys.argv) == 3 and sys.argv[1] == '--dedupe':
        try:
            before, after, removed, shaders, pairs, rejected = deduplicate(sys.argv[2])
        except (OSError, ValueError) as e:
            raise SystemExit(f'[RED] NVN capture dedupe failed: {e}') from e
        print(f'deduplicated complete captures: {before} -> {after}; removed {removed}; shaders {shaders}; pairs {pairs}; rejected {rejected}')
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
