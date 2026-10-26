# OT2 Mobile

**Octopath Traveler II, running natively on Mac — and next, on iPhone.** This is a fork of [nxnative](https://github.com/seedds/nxnative) that brings the Nintendo Switch release of *Octopath Traveler II* (1.1.1) to Apple devices: the game's own arm64 program runs directly on the Apple chip, and its graphics are rebuilt on Metal. It adds a classic-Metal (Metal 3) graphics backend so the game runs on **macOS 15 and iOS 18**, without waiting for Metal 4.

Platforms: Mac (Apple silicon, macOS 15 or later) · iPhone (A17 Pro or later, iOS 18 or later; packaging works, not yet tested on a device) · Game version: Switch 1.1.1 · License: MIT · **Bring your own game files**

中文: [README.zh-CN.md](README.zh-CN.md)

<p align="center">
  <img src="docs/images/tavern-explore.jpg" width="100%" alt="Agnea's tavern, free to walk around, with the minimap at the bottom right">
</p>
<p align="center">
  <img src="docs/images/title.jpg" width="32%" alt="The title screen with the HD-2D city background">
  <img src="docs/images/tavern-dialogue.jpg" width="32%" alt="Agnea on the tavern stage: You're all too kind…">
  <img src="docs/images/first-battle.jpg" width="32%" alt="The first battle in the forest, Gus and a winged foe">
</p>

## Status

| | |
|---|---|
| Mac | New game → Agnea's prologue in the tavern → out into her village → the first battle (attack, Boost, Break) → save and reload: all work, with sound, at the game's native 30 fps. |
| Stability | Ran 2 hours on the title screen's rotating scenes and 31 minutes in the tavern without a crash; about 2.6 GB resident at peak on the Mac. Memory still grows slowly (about 0.45 GB per hour); sessions longer than about 2 hours are untested. |
| Shaders | About 8,400 shaders are extracted straight from your game files at build time (no play-through needed); the rest are captured the first time the game uses them. A place whose shaders are not yet captured may show missing pieces the first time (see [Known limitations](#known-limitations)). |
| iPhone | The unsigned app builds for iOS 18 (A17 Pro and later). It has **not been run on a real device yet**. |


## What it is, and what it is not

**It is:**

- The game's own program **executing directly on Apple silicon**, with no emulated CPU. Only the few instructions that cannot run unchanged under Apple's kernel are rewritten (nxnative's NSO rewriter).
- nxnative's host for the Switch system services, plus a **classic-Metal NVN backend** derived from [d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)'s `DM_NVN_M3` branch, so it runs on macOS 15 / iOS 18 instead of requiring Metal 4.
- A game profile for Octopath Traveler II 1.1.1 (`dm/games/0100A3501946E000/`): an Unreal Engine allocator replacement, the memory layout, and the UE4 shader handling it needs.

**It is not:**

- An emulator, cloud gaming, or streaming.
- **A source of game content.** There is no game program, art, text, data or shader in this repository. Everything is generated on your own machine from your own game dump and keys.
- Online. The game runs fully offline.

## What this fork adds to nxnative

| Change | Where |
|---|---|
| Classic-Metal (Metal 3) NVN backend for macOS 15 / iOS 18, vendored from d2r-mobile with OT2 fixes | `dm/host/m3_routea_*`, `dm/host/m3gfx/` |
| Unreal Engine 4 allocator cut: FMallocBinned3 replaced by the host's malloc zone, so the game fits in a 3 GB virtual address space | `dm/host/hle_uemalloc.c`, `dm/games/0100A3501946E000/patches.py` |
| UE4 version-11 PAK inline shaders and a runtime-capture fallback for shaders that cannot be extracted statically | `dm/gfx/tools/uepak.py`, `shader_split.py`, `nvn_capture_split.py` |
| Static extraction of OT2's compact UEXP material shaders (standalone LZ4 records), merged with runtime captures by content key | `dm/gfx/tools/ot2_uexp_static.py` |
| Ported from upstream nxnative into the classic backend: integer fragment outputs, slice-writing geometry shaders folded into layered vertex shaders (UE's 3D color-grading LUT), and NVN depth-mode entry selection | `dm/host/m3_routea_nvn_mtl.m` |
| Friendlier Mac keyboard: Return/Space confirm, Esc cancel | `dm/host/front_mac.m` |

## Getting started (Mac)

You need an Apple silicon Mac on macOS 15 or later with Xcode 16 or later, your own **Octopath Traveler II** dump (XCI or NSP, version 1.1.1) and your console's `prod.keys`.

> This project provides only tools. It contains no game content and does not distribute, endorse or take responsibility for anyone distributing game files or packages that contain them. Use only a copy of the game that you own.

**1. Get the code and tools** (same as nxnative):

```
git clone https://github.com/leeashine/ot2-mobile.git && cd ot2-mobile
brew install xcodegen zstd spirv-cross glslang
brew install --cask dotnet-sdk
python3 -m pip install lz4 capstone fonttools "backports.zstd; python_version < '3.14'"
```

Use the full Xcode toolchain. If several Xcode versions are installed, prefer a scoped `DEVELOPER_DIR` so this build does not change other projects:

```sh
export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
xcodebuild -version
xcrun --sdk iphoneos --show-sdk-path
xcrun -find metal
```

Alternatively, select it system-wide with `sudo xcode-select --switch "/Applications/Xcode.app/Contents/Developer"`. The selected Xcode must include the iOS SDK and Metal tools.

**2. Build for the Mac** from the folder that holds your game dump:

```
python3 scripts/build_ipa_from_nsp.py ~/Games/OT2 -k ~/keys/prod.keys --platform mac
```

The classic-Metal sources are vendored; no `M3_GFX_DIR` environment variable is needed.

The script extracts the game, rewrites its code modules, translates the shaders it can find and builds the Mac host, then prints the command that runs the game.

For an opted-in NVN profile whose static split finds no shaders, the Mac build runs a headless capture boot and collects complete runtime shaders before building the libraries. When defined, the profile's `nvn_capture_keys` supplies `DM_KEYS` input. This is separate from the interactive game command printed after the build.

To collect shaders from an area not seen during the initial boot, run the printed Mac command, play through that area, then rerun the build:

```sh
python3 scripts/build_ipa_from_nsp.py ~/Games/OT2 -k ~/keys/prod.keys --platform mac --capture-more
```

`--capture-more` merges complete local captures and rebuilds without starting the headless capture boot.

**3. Play.** Click the game window first. A physical controller (Xbox, PlayStation, Switch Pro) works and is the most comfortable. On the keyboard:

| Key | Button |
|---|---|
| W A S D | Move (left stick) |
| Arrow keys | D-pad / menu navigation |
| Return / Space | A — confirm, talk |
| Esc / Delete | B — cancel |
| X / Tab | X — main menu |
| Y | Y |
| Q / E, Z / C | L / R, ZL / ZR |
| P / O | + / − |

## Getting started (iPhone)

<!-- TODO(verify): IPA packaging steps after the device test. -->

The same script packs an unsigned IPA for iOS 18 (A17 Pro and later). Sign it with the **Increased Memory Limit** capability (`com.apple.developer.kernel.increased-memory-limit`). It has not been run on a real device yet; reports are welcome.

## Known limitations

| Item | Status |
|---|---|
| Shader coverage | About 73% of the game's material shader records are extracted statically (each is a standalone LZ4 block). The other 27% use a variant whose format is not decoded yet; those shaders are captured at run time instead. The first Mac build also boots the game headless once to capture the title and opening; after visiting new areas, run the build again with `--capture-more`. |
| iPhone | Builds; not yet tested on a device. |
| Devices | Mac and iPhone builds target Apple silicon (A17 Pro / M1 and later). Intel Macs are not supported. |
| Online | Out of scope. |

## How it works

| Part | Where | What it does |
|---|---|---|
| Rewriter | `dm/tools` | Rewrites the few instructions that cannot run unchanged under Apple's kernel |
| Host | `dm/host` | Loads the rewritten program and provides the Switch system services |
| Graphics | `dm/host/m3_routea_*`, `dm/gfx` | NVN on classic Metal; shaders translated offline from the game's own (Ryujinx's translator → SPIR-V → SPIRV-Cross → Metal) |
| Game profile | `dm/games/0100A3501946E000` | OT2-specific memory layout and patches |
| iOS app | `dm/ios` | nxnative's app shell |

For details see nxnative's [docs/development.md](docs/development.md) and this fork's notes in [docs/ot2-macos-trial.md](docs/ot2-macos-trial.md).

## Legal

**You must own the game.** This is an independent, non-commercial project for learning. It is not affiliated with, endorsed by, or sponsored by Square Enix or Nintendo. OCTOPATH TRAVELER is a trademark of Square Enix; Nintendo Switch is a trademark of Nintendo. Screenshots are of the author's own copy and are shown to document the project; the game's content belongs to its owners.

## Acknowledgements

- **[nxnative](https://github.com/seedds/nxnative)** (seedds, MIT): the host, rewriter, shader pipeline, game-profile system and iOS shell this fork is built on, and the upstream fixes ported into the classic backend.
- **[d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)** (jhaizhou, MIT): the native-execution approach and the classic-Metal `DM_NVN_M3` backend.
- **Ryujinx / Ryubing** (MIT): the shader translator.
- Everything nxnative credits — Atmosphère, LibHac, SPIRV-Cross, glslang, deko3d, libvpx, stb_vorbis and more — see [dm/third_party](dm/third_party/README.md) and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## License

MIT, see [LICENSE](LICENSE). Third-party code keeps its own license; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
