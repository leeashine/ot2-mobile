"""Asset-free regression checks for the iPhone Duo display settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
from uepak import Pak


class DisplayConfigTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin', 'requires Foundation and clang')
    def test_native_planner_and_independent_pak_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary, pak = root / 'display-test', root / 'display.pak'
            subprocess.run(['clang', '-fobjc-arc', '-Wall', '-Werror',
                '-Wno-deprecated-declarations', '-framework', 'Foundation',
                str(REPO / 'dm/ios/Sources/DisplayConfig.m'),
                str(REPO / 'dm/ios/tests/t_display_config.m'), '-o', str(binary)],
                check=True, capture_output=True, text=True)
            subprocess.run([str(binary), str(pak)], check=True, capture_output=True, text=True)
            archive = Pak(pak)
            try:
                profile = archive.read('Test/Config.ini', lambda block, method: block)
            finally:
                archive.f.close()
            self.assertEqual(profile, b'[Docked]\nr.setres=2670x1878\n[Handheld]\nr.setres=2670x1878\n')

    def test_resolution_menu_requires_manifest_and_keeps_fps_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control, manifest, output = root / 'control.nacp', root / 'display.json', root / 'launcher.json'
            control.write_bytes(bytes(0x4000))
            manifest.write_text('{}')
            env = dict(os.environ)
            for key in ('DM_DISPLAY_CONFIG', 'DM_GAMES_FIRST', 'DM_GAMES_DIR'):
                env.pop(key, None)
            for enabled in (False, True):
                if enabled:
                    env['DM_DISPLAY_CONFIG'] = str(manifest)
                subprocess.run([sys.executable, str(REPO / 'dm/games/settings.py'),
                    '0100A3501946E000', str(root), str(control), str(output)],
                    env=env, check=True, capture_output=True, text=True)
                settings = {s['env']: s for s in json.loads(output.read_text())['settings']}
                self.assertEqual(settings['DM_FPS_TARGET']['default'], '30')
                self.assertEqual([o[0] for o in settings['DM_FPS_TARGET']['options']], ['30', '60'])
                self.assertEqual('DM_RESOLUTION' in settings, enabled)
                if enabled:
                    self.assertEqual(settings['DM_RESOLUTION']['default'], 'auto')
                    self.assertEqual([o[0] for o in settings['DM_RESOLUTION']['options']],
                                     ['auto', 'original', '2670x1878'])


if __name__ == '__main__':
    unittest.main()
