#!/usr/bin/env python3
"""Build/run an opt-in OT2 1.1.1 Mac widescreen experiment from existing local assets."""
import argparse
import gzip
import hashlib
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

REPO = Path(__file__).resolve().parents[1]
GAME = '0100A3501946E000'
BUILD = '65619a04b8a04b10d44f9996ef141062'


def ratio(value):
    try:
        parts = [float(p) for p in value.split(':')]
        result = parts[0] / parts[1] if len(parts) == 2 else parts[0] if len(parts) == 1 else 0
        if not math.isfinite(result) or not 1 <= result <= 3.6:
            raise ValueError()
        return result
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError('aspect must be between 1:1 and 3.6:1')


def overlay(work, output, width, height):
    # Only a generated copy of the user's config is placed in the local overlay.
    # A legacy v4 pak needs no encryption or game key. Leave the original pak intact.
    sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
    from uepak import Pak
    pak = Pak(work / 'extract/v0/RomFS/Majesty/Content/Paks/Majesty-Switch.pak')
    name = 'Majesty/Config/Switch/SwitchDeviceProfiles.ini'
    data = pak.read(name, lambda block, method: zlib.decompress(block))
    for old in (b'r.setres=1920x1080', b'r.setres=1280x720'):
        if data.count(old) != 1:
            raise RuntimeError('unrecognized device profile: expected one of each resolution')
        data = data.replace(old, f'r.setres={width}x{height}'.encode())
    def fstr(s):
        b = s.encode() + b'\0'
        return struct.pack('<i', len(b)) + b
    entry = struct.pack('<qqqi', 0, len(data), len(data), 0) + hashlib.sha1(data).digest() + struct.pack('<BI', 0, 0)
    body = entry + data
    index = fstr(pak.mount) + struct.pack('<i', 1) + fstr(name) + entry
    footer = b'\0' + struct.pack('<IIQQ', 0x5A6F12E1, 4, len(body), len(index)) + hashlib.sha1(index).digest()
    dest = output / 'Majesty/Content/Paks/ZZ_WideTest_P.pak'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body + index + footer)
    if Pak(dest).read(name, lambda block, method: zlib.decompress(block)) != data:
        raise RuntimeError('generated overlay failed readback')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True, help='existing 0100A3501946E000_build folder')
    p.add_argument('--aspect', type=ratio, default=ratio('21:9'))
    p.add_argument('--height', type=int, choices=(720, 1080, 1338), default=1080, help='output height; game screen percentage remains unchanged')
    p.add_argument('--fps', type=int, choices=(30, 60), default=60)
    p.add_argument('--build', action='store_true', help='rebuild host/modules before playing')
    p.add_argument('--headless', action='store_true', help='render without a window/audio for diagnostics')
    p.add_argument('--native-camera', action='store_true', help='comparison: leave the camera at its original aspect/FOV')
    p.add_argument('--run-name', default='play', help='separate save/log directory within wide-test')
    a = p.parse_args()
    if Path(a.run_name).name != a.run_name or a.run_name in ('', '.', '..'):
        p.error('run-name must be a single directory name')
    w = a.work.expanduser().resolve()
    if w.is_relative_to(REPO):
        p.error('game assets must be outside the repository')
    with (w / 'extract/v0/ExeFS/main').open('rb') as f:
        header = f.read(0x60)
    if header[:4] != b'NSO0' or header[0x40:0x50].hex() != BUILD:
        raise RuntimeError('only the verified OT2 1.1.1 main build is supported')
    root = w / 'wide-test'
    if shutil.disk_usage(w).free < 9 * 1024**3:
        raise RuntimeError('at least 9 GiB free space is required for this diagnostic run')
    env = dict(os.environ, DM_GAMES_DIR=str(w / 'nvn-profile'), DM_GAMES_FIRST='1')
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env['PATH']
    if a.build:
        sys.path.insert(0, str(REPO / 'dm/games'))
        import game
        import build_ipa_from_nsp as builder
        os.environ.update(env)
        logs = root / 'build-logs'
        logs.mkdir(parents=True, exist_ok=True)
        g = game.load(GAME)
        builder.build_mac_host(REPO, root / 'dmhost', env, logs, g)
        builder.rewrite(Path(sys.executable), REPO, w / 'extract/v0/ExeFS', root / 'patched', env, logs, g)
    obs = root / 'patched/main.obs.tsv'
    if not (root / 'dmhost').is_file() or not obs.is_file() or not all(
            site in obs.read_text() for site in ('277d644', '23144ac')):
        raise RuntimeError('missing widescreen build: run once with --build')
    run = root / a.run_name
    run.mkdir(parents=True, exist_ok=True)
    if (run / 'pid').is_file():
        try:
            os.kill(int((run / 'pid').read_text()), 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('this run is already active; close its window or choose another --run-name')
    for name in ('save', 'temp'):
        (run / name).mkdir(exist_ok=True)
    width = round(a.height * a.aspect / 2) * 2
    aspect = width / a.height
    overlay(w, run / 'overlay', width, a.height)
    (run / 'ctl').write_text('')
    env.update(DM_ROOT=str(w), DM_ROMFS=str(w / 'extract/v0/RomFS'),
               DM_ROMFS_OVERLAY=str(run / 'overlay'), DM_SAVE=str(run / 'save'),
               DM_TEMP=str(run / 'temp'), DM_MSL_DIR=str(w / 'shader/cache'),
               DM_FONT_DIR=str(w / 'font'), DM_NVN_SHMAP=str(w / f'nvn-profile/{GAME}/shader_map.tsv'),
               OT2_NVN_HLE='1', OT2_NVN_OFFLINE_SHADERS='1', OT2_NVN_CAPTURE_EVERY='0',
               DM_LANG='zh-Hans', DM_FPS_TARGET=str(a.fps), DM_CTL=str(run / 'ctl'),
               DM_NVN_TSV=str(run / 'frames.tsv'), DM_NVN_TSV_CALLS='0', DM_NVN_FRAMES='0')
    env.pop('DM_CAMERA_ASPECT', None)
    env.pop('DM_HUD_ASPECT', None)
    env.pop('DM_WINDOW', None)
    env.pop('DM_AUDIO', None)
    env.pop('DM_WINDOW_ASPECT', None)
    if not a.native_camera:
        env['DM_CAMERA_ASPECT'] = str(aspect)
        env['DM_HUD_ASPECT'] = str(aspect)
    if not a.headless:
        env.update(DM_WINDOW='1', DM_AUDIO='1', DM_WINDOW_ASPECT=str(aspect))
    print(f'OT2 Mac test: {width}x{a.height}, aspect {aspect:.6f}, {a.fps} fps', flush=True)
    print(f'Separate save: {run / "save"}\nLog: {run / "game.log"}', flush=True)
    cmd = [str(root / 'dmhost'), str(root / 'patched'), '--', '-SwitchVirtualAddressSpaceSize=4064',
           f'-ResX={width}', f'-ResY={a.height}', '-ForceRes']
    with (run / 'game.log').open('w') as log:
        process = subprocess.Popen(cmd, env=env, cwd=run, stdout=log, stderr=subprocess.STDOUT)
        (run / 'pid').write_text(str(process.pid))
        try:
            status = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                status = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                status = process.wait()
    (run / 'pid').unlink(missing_ok=True)
    with (run / 'game.log').open('rb') as source, gzip.open(run / 'game.log.gz', 'wb') as dest:
        shutil.copyfileobj(source, dest)
    (run / 'game.log').unlink()
    return status


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'[RED] {error}', file=sys.stderr)
        sys.exit(1)
