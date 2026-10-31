#!/usr/bin/env python3
"""Export the OT2 iPhone Duo adaptation as an unsigned iOS IPA."""
import argparse
import json
import zlib
import os
from pathlib import Path
import subprocess
import sys

from play_ot2_widescreen import BUILD, GAME, REPO


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, help='Destination IPA; defaults to the automatic-display test filename')
    a = p.parse_args()
    w = a.work.expanduser().resolve()
    if w.is_relative_to(REPO):
        p.error('game assets must be outside the repository')
    with (w / 'extract/v0/ExeFS/main').open('rb') as f:
        header = f.read(0x60)
    if header[:4] != b'NSO0' or header[0x40:0x50].hex() != BUILD:
        raise RuntimeError('only the verified OT2 1.1.1 build is supported')
    root = w / 'wide-test'
    obs = (root / 'patched/main.obs.tsv').read_text()
    if not all(site in obs for site in ('277d644', '23144ac')):
        raise RuntimeError('build the widescreen modules on Mac first')
    stage = root / 'ios-auto'
    stage.mkdir(parents=True, exist_ok=True)
    romfs = w / 'extract/v0/RomFS'
    sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
    from uepak import Pak
    pak = Pak(romfs / 'Majesty/Content/Paks/Majesty-Switch.pak')
    name = 'Majesty/Config/Switch/SwitchDeviceProfiles.ini'
    profile = pak.read(name, lambda block, method: zlib.decompress(block)).decode('utf-8')
    for old in ('r.setres=1920x1080', 'r.setres=1280x720'):
        if profile.count(old) != 1:
            raise RuntimeError('unrecognized device profile resolution')
        profile = profile.replace(old, 'r.setres=${DISPLAY_RESOLUTION}')
    config = stage / 'display.json'
    config.write_text(json.dumps(dict(game=GAME, build=BUILD, mount=pak.mount, path=name,
        overlay_path='Majesty/Content/Paks/ZZ_WideTest_P.pak', profile=profile)), encoding='utf-8')
    env_file = stage / 'wide.env'
    # Auto is the launcher's editable default, not an env-file override.
    env_file.write_text('OT2_NVN_CAPTURE_EVERY=0\n')
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
               GAME=GAME, DM_GAMES_DIR=str(w / 'nvn-profile'), DM_GAMES_FIRST='1',
               W=str(stage / 'ipa'), PATCHED=str(root / 'patched'), ROMFS=str(romfs),
               MSL_IOS=str(w / 'shader/ios'), GFXAPI='nvn', FONT_PY=sys.executable,
               DM_DISPLAY_NAME='OT2 Wide Test', DM_BUNDLE_ID=f'org.nxnative.{GAME.lower()}.widetest',
               DM_APP_VERSION='1.1.1', DM_LANG='zh-Hans', DM_SHOW_FPS='1',
               DM_ICON=str(w / 'extract/v0/icon.jpg'), AOC=str(w / 'aoc'),
               DM_ENV_FILE=str(env_file), DM_DISPLAY_CONFIG=str(config))
    out = a.output.expanduser().resolve() if a.output else w.parent / 'OctopathTravelerII-1.1.1-iPhoneDuo-unsigned.ipa'
    if out.is_relative_to(REPO):
        p.error('the IPA must be outside the repository')
    return subprocess.call(['bash', str(REPO / 'dm/ios/tools/build_ipa.sh'), str(out)], env=env, cwd=REPO)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'[RED] {error}', file=sys.stderr)
        sys.exit(1)
