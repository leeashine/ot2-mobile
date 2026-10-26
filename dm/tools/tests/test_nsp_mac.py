"""NSP script Mac-only build (scripts/build_ipa_from_nsp.py --platform mac): the shader steps build only the Mac's libraries, each output keeps its own reuse key, a Mac-only build is
reused after an iOS build (which builds the Mac's too) and an iOS build is not reused after a Mac-only one, neither key without the Mac libraries' stamp (inputs.tsv, which the one
chain version's c1_full.tsv / cb_extent.tsv name); the run command's environment file is read as the iOS app reads it.
No game files, keys or Xcode needed (temporary files only in a temporary folder)."""
import importlib.util
import json
import os
import struct
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / 'scripts/build_ipa_from_nsp.py'
spec = importlib.util.spec_from_file_location('build_ipa_from_nsp', SCRIPT)
nsp = importlib.util.module_from_spec(spec); spec.loader.exec_module(nsp)
CHAIN, INPUTS = '0123456789ab', 'aaaaaaaaaaaa'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.tmp)
        self.sh, self.logs, self.ran = self.tmp / 'shader', self.tmp / 'logs', []
        self.logs.mkdir()
        for cm in (mock.patch.object(nsp, 'PROG', mock.Mock()), mock.patch.object(nsp, 'say', lambda m: None), mock.patch.object(nsp, 'run', self.fake_run)):
            cm.__enter__(); self.addCleanup(cm.__exit__, None, None, None)

    def fake_run(self, cmd, log, env=None, cwd=None, on_line=None):   # stands in for the translators: writes the libraries a real run writes
        self.ran.append(([str(c) for c in cmd], dict(env or {})))
        tool = Path(cmd[1]).name
        if tool in ('vk_shaders.py', 'gl_shaders.py'):
            api, a = tool[:2], [str(c) for c in cmd]
            outs = [Path(a[a.index('--ios') - 1]), Path(a[a.index('--ios') + 1])] if '--ios' in a else [Path(a[-1])]
            for o in outs: (o / api).mkdir(parents=True, exist_ok=True); (o / api / f'{api}_shaders.metallib').write_bytes(b'lib')
            log.write_text('macosx: 3 shaders\n' + ('iphoneos: 3 shaders\n' if '--ios' in a else ''))
        elif tool == 'own_compilers.py':   # a full dmsh_build.py run: the libraries, their stamp, and the profile's tables naming it
            outs = [self.sh / 'cache'] + ([Path(env['IOSOUT'])] if 'IOSOUT' in env else [])
            for o in outs:
                (o / f'b-{CHAIN}').mkdir(parents=True, exist_ok=True); (o / f'b-{CHAIN}' / 'k_b.metallib').write_bytes(b'lib')
                (o / f'b-{CHAIN}' / 'inputs.tsv').write_text(f'# stamp\ngame\t0100535012974000\ninputs\t{INPUTS}\n')
            for n in ('c1_full.tsv', 'cb_extent.tsv'): (self.tmp / n).write_text(f'# chain b-{CHAIN} inputs {INPUTS} 2026-10-23T00:00:00+00:00\n')
            log.write_text('shaders 1: ok 1\n')


class Layer(Base):
    def vk(self, mac, key='K'):
        self.ran.clear()
        return nsp.layer_shaders(sys.executable, REPO, 'vk', 'Vulkan', [self.tmp / 'romfs'], self.sh, key, self.logs, {'WORK': str(self.tmp)}, mac)

    def test_mac_only(self):   # no --ios, only the Mac key, the Mac folder for DM_MSL_DIR
        self.assertEqual(self.vk(True), self.sh)
        self.assertNotIn('--ios', self.ran[0][0])
        self.assertTrue((self.sh / 'vk.key').is_file()); self.assertFalse((self.sh / 'ios/vk.key').exists())
        self.assertEqual(self.vk(True), self.sh); self.assertEqual(self.ran, [])   # reused

    def test_mac_after_ios(self):   # an iOS build makes the Mac library too: a Mac-only build is reused
        self.assertEqual(self.vk(False), self.sh / 'ios')
        self.assertIn('--ios', self.ran[0][0])
        (self.sh / 'vk.key').unlink()   # an iOS build from before Mac-only builds wrote only its own key
        self.assertEqual(self.vk(True), self.sh); self.assertEqual(self.ran, [])

    def test_ios_after_mac(self):   # a Mac-only build made no iPhone library: an iOS build runs
        self.vk(True)
        self.assertEqual(self.vk(False), self.sh / 'ios'); self.assertEqual(len(self.ran), 1)
        self.assertTrue((self.sh / 'ios/vk/vk_shaders.metallib').is_file())

    def test_changed_inputs(self):
        self.vk(False)
        self.vk(True, 'K2'); self.assertEqual(len(self.ran), 1)
        self.assertTrue((self.sh / 'ios/vk/vk_shaders.metallib').is_file())   # the iPhone library stays, under its own (older) key
        self.assertEqual(nsp.reused(self.sh / 'ios/vk.key', 'K'), '3 shaders for the Mac and iOS')


class Nvn(Base):
    def setUp(self):
        super().setUp()
        self.g = types.SimpleNamespace(table=lambda n: self.tmp / n, dir=self.tmp)
        for cm in (mock.patch.object(nsp, 'fingerprint', lambda *a, **k: 'K'), mock.patch.object(nsp, 'chain_of', lambda repo: CHAIN)):   # one chain version for every game
            cm.__enter__(); self.addCleanup(cm.__exit__, None, None, None)

    def build(self, mac):
        self.ran.clear()
        return nsp.build_shaders(sys.executable, REPO, self.sh, REPO / 'dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate', {'WORK': str(self.tmp), 'IOSOUT': '/elsewhere'}, self.logs, self.g, pkg_key='P', mac=mac)

    def test_mac_only(self):   # no IOSOUT (not even the caller's), the Mac key beside the cache folder, not in it
        self.assertEqual(self.build(True), self.sh / 'cache')
        self.assertNotIn('IOSOUT', self.ran[0][1])
        self.assertTrue((self.sh / f'mac-b-{CHAIN}.key').is_file()); self.assertEqual([p.name for p in (self.sh / 'cache').iterdir()], [f'b-{CHAIN}'])
        self.assertEqual(self.build(True), self.sh / 'cache'); self.assertEqual(self.ran, [])

    def test_mac_after_ios(self):
        self.assertEqual(self.build(False), self.sh / 'ios')
        self.assertEqual(self.ran[0][1]['IOSOUT'], str(self.sh / 'ios'))
        (self.sh / f'mac-b-{CHAIN}.key').unlink()   # an iOS build from before Mac-only builds
        self.assertEqual(self.build(True), self.sh / 'cache'); self.assertEqual(self.ran, [])

    def test_ios_after_mac(self):
        self.build(True)
        self.assertEqual(self.build(False), self.sh / 'ios'); self.assertEqual(len(self.ran), 1)

    def test_no_stamp(self):   # Mac libraries no full build stamped (an interrupted one): no table can name them, so neither key reuses them
        self.build(False)
        (self.sh / 'cache' / f'b-{CHAIN}' / 'inputs.tsv').unlink()
        self.assertEqual(self.build(True), self.sh / 'cache'); self.assertEqual(len(self.ran), 1)
        self.assertTrue((self.sh / 'cache' / f'b-{CHAIN}' / 'inputs.tsv').is_file())

    def test_stale_tables(self):   # a reused build makes a table again when it does not name the Mac libraries' stamp
        self.build(True)
        (self.tmp / 'cb_extent.tsv').write_text(f'# chain b-{CHAIN} inputs bbbbbbbbbbbb 2026-10-23T00:00:00+00:00\n')
        self.assertEqual(self.build(True), self.sh / 'cache'); self.assertEqual([Path(c[1]).name for c, _ in self.ran], ['cb_extent.py'])


class EnvFile(Base):
    def test_pairs(self):
        p = self.tmp / 'env.txt'; p.write_text('# a comment\nDM_A=1\n  DM_B = x=y\n=nokey\nnoeq\n\nDM_C=\n')
        self.assertEqual(nsp.env_file_pairs(p), {'DM_A': '1', 'DM_B': ' x=y', 'DM_C': ''})

    def test_missing(self):
        with self.assertRaises(nsp.BuildError): nsp.env_file_pairs(self.tmp / 'none.txt')


class NvnCapturePlan(unittest.TestCase):
    def test_first_build_captures_without_complete_snapshots(self):
        self.assertEqual(nsp.nvn_capture_plan('nvn', True, False, False), 'capture')
        self.assertEqual(nsp.nvn_capture_plan('nvn', True, True, False), 'static')
        self.assertEqual(nsp.nvn_capture_plan('nvn', False, False, False), 'static')
        self.assertEqual(nsp.nvn_capture_plan('nvn', True, False, True), 'merge')
        with self.assertRaises(nsp.BuildError): nsp.nvn_capture_plan('nvn', False, False, True)
    def test_capture_more_is_a_cli_option(self):
        self.assertTrue(nsp.parse_args(['--capture-more']).capture_more)



class NvnCaptureFiles(unittest.TestCase):
    def test_counts_only_complete_data_control_pairs(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        good = '123-0000000000000001-0'
        bad = '123-0000000000000002-0'
        (root / f'{good}.prefix.bin').write_bytes(b'code')
        (root / f'{good}.control.bin').write_bytes(bytes(0x880))
        (root / f'{good}.meta.json').write_text(json.dumps({
            'dataBytes': 4, 'dataComplete': True, 'controlBytes': 0x880, 'controlComplete': True,
        }))
        (root / f'{bad}.prefix.bin').write_bytes(b'code')
        (root / f'{bad}.control.bin').write_bytes(bytes(0x708))
        (root / f'{bad}.meta.json').write_text(json.dumps({
            'dataBytes': 4, 'dataComplete': True, 'controlBytes': 0x708, 'controlComplete': False,
        }))
        self.assertEqual(nsp.nvn_capture_complete(root), {good})


class NvnCaptureFacts(unittest.TestCase):
    def test_runtime_facts_merge_with_profile_and_manual_rows(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        profile = root / 'profile'; profile.mkdir()
        (profile / 'shader_facts.tsv').write_text('# generated\nold\t{"base":1}\nboth\t{"common":"profile"}\n')
        (profile / 'shader_facts_manual.tsv').write_text('# manual\nboth\t{"common":"manual"}\n')
        runtime = root / 'runtime.tsv'
        runtime.write_text('# runtime\nboth\t{"common":"capture","local":[8,8,1],"shared":0}\nnew\t{"local":[4,4,1],"shared":16}\n')
        self.assertEqual(nsp.merge_nvn_shader_facts(profile, runtime), {
            'old': {'base': 1},
            'both': {'common': 'manual', 'local': [8, 8, 1], 'shared': 0},
            'new': {'local': [4, 4, 1], 'shared': 16},
        })


class NvnCaptureProfile(unittest.TestCase):
    def test_capture_tables_are_isolated_from_repository_profile(self):
        patcher = mock.patch.dict(os.environ, {})
        patcher.start(); self.addCleanup(patcher.stop)
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        source = root / 'source' / '0100A3501946E000'; source.mkdir(parents=True)
        (source / 'game.tsv').write_text('nvn_capture\ton\n')
        (source / 'shader_map.tsv').write_text('repository-owned-map\n')
        (source / 'shader_facts_manual.tsv').write_text('# repo manual facts\n')
        work = root / 'build'; work.mkdir()
        other = root / 'other-profiles'; other.mkdir()
        env = {'DM_GAMES_DIR': str(other)}
        profile = types.SimpleNamespace(id='0100A3501946E000', dir=source)
        isolated = nsp.isolate_nvn_capture_profile(profile, work, env)
        self.assertEqual(isolated, work / 'nvn-profile' / profile.id)
        self.assertEqual((source / 'shader_map.tsv').read_text(), 'repository-owned-map\n')
        self.assertNotIn('repository-owned-map', (isolated / 'shader_map.tsv').read_text())
        manual = isolated / 'shader_facts_manual.tsv'
        self.assertEqual(manual.read_text(), '# repo manual facts\n')
        manual.write_text('# local runtime override\n')
        nsp.isolate_nvn_capture_profile(profile, work, env)
        self.assertEqual(manual.read_text(), '# local runtime override\n')
        self.assertEqual(env['DM_GAMES_DIR'].split(os.pathsep), [str(isolated.parent), str(other)])
        self.assertEqual(env['DM_GAMES_FIRST'], '1')


class NvnCaptureMerge(unittest.TestCase):
    def test_capture_more_rebuilds_from_old_and_new_complete_snapshots(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        work, logs = root / 'build', root / 'logs'
        profile = root / 'profile' / '0100A3501946E000'
        pending = work / 'shaders/pending'
        work.mkdir(); logs.mkdir(); profile.mkdir(parents=True); pending.mkdir(parents=True)
        game = types.SimpleNamespace(id='0100A3501946E000', dir=profile, table=lambda name: profile / name)
        env = {'DM_GAME': game.id}

        def add_capture(serial, marker, index=0):
            stem = f'123-{serial:016x}-{index}'
            control, code = bytearray(0x880), bytearray(0x80)
            control[:4] = bytes.fromhex('34127698')
            struct.pack_into('<I', control, 0x20, 0x880)
            struct.pack_into('<I', control, 0x704, len(code))
            code[:4] = bytes.fromhex('78563412')
            struct.pack_into('<I', code, 0x30, 5 << 10)
            code[0x60] = marker
            (pending / f'{stem}.control.bin').write_bytes(control)
            (pending / f'{stem}.prefix.bin').write_bytes(code)
            (pending / f'{stem}.meta.json').write_text(json.dumps({
                'controlBytes': len(control), 'controlComplete': True, 'dataBytes': len(code),
                'dataComplete': True, 'dataHeaderBytes': 48,
            }))

        add_capture(1, 1)
        first = nsp.build_nvn_capture_package(REPO, sys.executable, work, env, logs, game)
        package = work / 'shader/pkg/ps_capture.bin'
        self.assertEqual(package.read_bytes().count(b'BTCDBTCD'), 1)
        add_capture(1, 1, index=1)
        add_capture(2, 2)
        result = nsp.build_nvn_capture_package(REPO, sys.executable, work, env, logs, game)
        self.assertNotEqual(result, first)
        self.assertEqual(package.read_bytes().count(b'BTCDBTCD'), 2)
        rows = [line for line in (profile / 'shader_map.tsv').read_text().splitlines()
                if line and not line.startswith('#') and not line.startswith('package')]
        self.assertEqual(len(rows), 2)
        self.assertEqual((profile / 'shader_map.tsv.conflicts.tsv').read_text(), '')
        self.assertEqual(len(nsp.nvn_capture_complete(pending)), 2)


class NvnCaptureDedupe(unittest.TestCase):
    def test_per_key_dedup_keeps_collected_shader_and_pair_sets(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        pending = root / 'pending'; pending.mkdir()
        splitter = REPO / 'dm/gfx/tools/nvn_capture_split.py'

        def add_capture(program, index, stage, marker):
            stem = f'123-{program:016x}-{index}'
            control, code = bytearray(0x880), bytearray(0x80)
            control[:4] = bytes.fromhex('34127698')
            struct.pack_into('<I', control, 0x20, len(control))
            struct.pack_into('<I', control, 0x704, len(code))
            code[:4] = bytes.fromhex('78563412')
            struct.pack_into('<I', code, 0x30, ({'vs': 1, 'ps': 5}[stage] << 10) | 1)
            code[0x60] = marker
            (pending / f'{stem}.prefix.bin').write_bytes(code)
            (pending / f'{stem}.control.bin').write_bytes(control)
            (pending / f'{stem}.meta.json').write_text(json.dumps({
                'controlBytes': len(control), 'controlComplete': True,
                'dataBytes': len(code), 'dataComplete': True, 'dataHeaderBytes': 48,
            }))

        add_capture(1, 0, 'vs', 1)
        add_capture(1, 1, 'ps', 2)
        add_capture(2, 0, 'vs', 1)  # Same shader key, another program-pair association.
        add_capture(2, 1, 'ps', 3)

        def collect_outputs(label):
            out = root / label; out.mkdir()
            package, mapping, facts, pairs = (out / name for name in ('pkg', 'map.tsv', 'facts.tsv', 'pairs.tsv'))
            result = subprocess.run([sys.executable, str(splitter), str(pending), str(package),
                                     str(mapping), str(facts), str(pairs)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            keys = {line.split('\t')[3] for line in mapping.read_text().splitlines()
                    if line and not line.startswith('#') and not line.startswith('package')}
            pair_set = {tuple(line.split('\t')) for line in pairs.read_text().splitlines()
                        if line and not line.startswith('#')}
            return keys, pair_set

        before_keys, before_pairs = collect_outputs('before')
        result = subprocess.run([sys.executable, str(splitter), '--dedupe', str(pending)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after_keys, after_pairs = collect_outputs('after')
        self.assertEqual(after_keys, before_keys)
        self.assertEqual(after_pairs, before_pairs)
        self.assertEqual(len(nsp.nvn_capture_complete(pending)), 3)
        self.assertEqual(len(list(pending.glob('*.meta.json'))), 3)




class NvnCaptureEmptySplit(unittest.TestCase):
    def test_empty_opted_in_split_keeps_existing_package_untouched(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        pkg, logs = root / 'shader/pkg', root / 'logs'
        pkg.mkdir(parents=True); logs.mkdir()
        (pkg / 'old.bin').write_bytes(b'previous package')
        def run_empty(cmd, log, env=None, cwd=None, on_line=None):
            Path(log).write_text('shaders: 0 (no static shader records)\n')
        with mock.patch.object(nsp, 'run', run_empty), mock.patch.object(nsp, 'PROG', mock.Mock()):
            result = nsp.split_shaders(sys.executable, REPO, [], [], pkg, {}, logs,
                types.SimpleNamespace(id='0100A3501946E000'), provisional=True, allow_empty=True)
        self.assertIs(result, False)
        self.assertEqual((pkg / 'old.bin').read_bytes(), b'previous package')
        self.assertFalse(pkg.with_name('pkg.partial').exists())


class NvnCaptureNoBoot(unittest.TestCase):
    def test_capture_more_without_snapshots_does_not_start_host(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        work, logs = root / 'build', root / 'logs'
        profile = root / 'profile'; profile.mkdir(parents=True)
        work.mkdir(); logs.mkdir()
        g = types.SimpleNamespace(id='0100A3501946E000', dir=profile, table=lambda name: profile / name)
        with mock.patch.object(nsp, 'build_mac_host') as host, mock.patch.object(nsp, 'boot_mac') as boot:
            with self.assertRaises(nsp.BuildError):
                nsp.capture_nvn_shaders(REPO, sys.executable, work, root, root / 'patched', None, 'en-US',
                                        {'DM_GAME': g.id}, logs, g, auto_boot=False)
        host.assert_not_called(); boot.assert_not_called()


class NvnCaptureBootInput(unittest.TestCase):
    def test_headless_capture_waits_for_the_profile_dm_keys_route(self):
        root = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, root)
        work, logs = root / 'build', root / 'logs'
        profile = root / 'profile'; profile.mkdir()
        pending = work / 'shaders/pending'
        pending.mkdir(parents=True); logs.mkdir()
        route = '20:A*15/3'
        g = types.SimpleNamespace(id='0100A3501946E000', dir=profile,
                                  table=lambda name: profile / name,
                                  get=lambda key, default=None: {'nvn_capture_keys': route}.get(key, default))
        now = [0.0]

        def fake_boot(host, patched, env, rd, log, secs, done):
            self.assertEqual(env['DM_KEYS'], route)
            stem = '123-0000000000000001-0'
            data, control = b'code', bytes(0x880)
            (pending / f'{stem}.prefix.bin').write_bytes(data)
            (pending / f'{stem}.control.bin').write_bytes(control)
            (pending / f'{stem}.meta.json').write_text(json.dumps({
                'controlBytes': len(control), 'controlComplete': True,
                'dataBytes': len(data), 'dataComplete': True,
            }))
            now[0] = 30
            self.assertFalse(done())
            now[0] = 62
            self.assertFalse(done())
            now[0] = 63
            self.assertTrue(done())
            return 0

        with mock.patch.object(nsp, 'build_mac_host', return_value=root / 'dmhost'), \
             mock.patch.object(nsp, 'boot_mac', side_effect=fake_boot), \
             mock.patch.object(nsp, 'build_nvn_capture_package', return_value='package-key'), \
             mock.patch.object(nsp.time, 'monotonic', side_effect=lambda: now[0]), \
             mock.patch.object(nsp, 'PROG', mock.Mock()), mock.patch.object(nsp, 'say', lambda m: None):
            result = nsp.capture_nvn_shaders(REPO, sys.executable, work, root, root / 'patched', None,
                                            'en-US', {}, logs, g, auto_boot=True)
        self.assertEqual(result, 'package-key')


if __name__ == '__main__':
    unittest.main()
