# OCTOPATH TRAVELER II: iPhone Duo adaptation

This opt-in adaptation targets OT2 1.1.1, main build
`65619a04b8a04b10d44f9996ef141062`. It adds a pre-game resolution menu,
uses the active iOS window for automatic sizing, and adjusts the game camera
and HUD to the display ratio. The same camera adaptation can be tested on Mac.

## Settings and behavior

Display-enabled builds offer these choices before **Play**:

| Resolution | Behavior |
| --- | --- |
| Auto (default) | Match the active window ratio, with even dimensions, at most 2,073,600 pixels and a 2520-pixel maximum dimension; no supersampling. |
| Original (16:9) | Use the game's original resolution and the existing 16:9 presentation. |
| iPhone Duo unfolded (2670 x 1878) | Use the full fixed preset, with higher GPU and memory demand. |

The Duo preset follows the native dimensions reported by the test device;
it is distinct from its 2853x2007 logical pixel canvas. Auto derives dimensions
from the active window and its screen scale, without identifying a device model.
For example, 951x669 points at scale 3 produces 1716x1206 output.

The selection is saved and applied when Play is pressed, without restarting
from the launcher. Changing the display ratio during gameplay still requires
restarting the game. This is startup adaptation, not dynamic resolution scaling.
The game's existing internal screen-percentage settings remain in effect.

Wider windows add horizontal world content; narrower windows, including the
unfolded Duo, add vertical content. HUD roots stay in a centered 16:9 safe area,
while full-picture fades and dialogue use their appropriate viewport layout.
The character-selection map retains its authored 16:9 projection and picking
coordinates. Title screens, movies, and authored cinematic bars may remain.
The adapter does not crop or stretch the completed game image.

The separate [frame-rate notes](ot2-framerate-test.md) describe the 30/60 fps
selector. Environment-file overrides continue to take precedence over the UI.

## Build and run

Use the project's Python environment and an existing extracted/built game:

```sh
.venv/bin/python scripts/play_ot2_widescreen.py \
  --work /path/to/0100A3501946E000_build --build --aspect 21:9 --height 1080 --fps 60
.venv/bin/python scripts/export_ot2_widescreen.py \
  --work /path/to/0100A3501946E000_build --output /path/to/OT2-iPhoneDuo-unsigned.ipa
```

The Mac runner accepts ratios from 1:1 to 3.6:1, heights 720/1080/1338 and
30/60 fps. Omit `--build` after the first build. `--native-camera` compares the
original projection at the same output resolution; `--headless` disables the
window and audio. `--run-name` selects a separate save/log folder in `wide-test`.
Game assets, generated overlays, build products and saves remain outside this
repository. Both scripts reject a different game executable build.

The exporter writes `dm/display.json` from the user's extracted Switch device
profile and includes it through `DM_DISPLAY_CONFIG`. The launcher shows the
resolution menu only for builds with that manifest. Immediately before guest
boot, the iOS front end writes a small Unreal v4 pak under `DM_TEMP`, updates
`DM_ROMFS_OVERLAY`, `DM_CAMERA_ASPECT`, `DM_HUD_ASPECT` and `DM_VIEW_ASPECT`
together, and uses a full-window Metal view. Existing overlays follow the
new one. The original game archive is unchanged. The output IPA is unsigned;
this script does not install it or modify device signing.

`DM_RESOLUTION` accepts `auto`, `original` and `2670x1878`. For older env files,
`DM_DISPLAY_AUTO=0` selects Original when `DM_RESOLUTION` is absent.

## Implementation and address evidence

- `DM_ROMFS_OVERLAY` adds a small generated `ZZ_WideTest_P.pak` containing the
  user's modified `SwitchDeviceProfiles.ini`. CLI `-ResX/-ResY` alone was
  overwritten during startup. The overlay retains the chosen output dimensions.
- Configuration-only 2520x1080 tests, including `AspectRatio_MaintainYFOV`, still
  rendered a 16:9 scene between pillars. Presentation scaling cannot fix this.
- The reflected `SetAspectRatio` thunk at main+`0x2f1759c` writes the camera
  component's float at +`0x204`. `GetCameraView` copies it into
  `FMinimalViewInfo`+`0x2c` at `0x277d508`/`0x277d50c` and writes FOV at +`0x18`
  at `0x277d504`. Projection mode is copied to +`0x31` at `0x277d538`.
- The new observation gate is at the shared epilogue, `0x277d644`, before
  `ldp d9, d8, [sp, #0x130]` (word `6d5323e9`). x19 still points to the freshly
  produced view, and x9-x17 carry no live values into the return. The rewriter
  verifies the instruction and scratch-register condition, gated by build ID.
- `hle_widescreen.c` also checks that build ID and only acts with
  `DM_CAMERA_ASPECT`. It skips orthographic views and invalid projection values.
  It writes the output view, not the persistent camera component, avoiding
  cumulative FOV changes. Horizontal FOV becomes
  `2 * atan(tan(oldFOV / 2) * newAspect / oldAspect)` for wider displays;
  vertical FOV is preserved. Narrower displays keep the original horizontal FOV
  and extend the vertical view instead (Vert+), preserving existing world content.
- `DM_WINDOW_ASPECT` is a general optional Mac front-end setting, independent of
  the camera patch. No shader translation or presentation-stretch changes.
- `DM_HUD_ASPECT` centers full-viewport UMG widgets inside a 16:9 safe area.
  The `GetAnchorsInViewport` getter at `0x23144ac` reads the four floats at
  widget+`0x210`; its reflected thunk at `0x23bdb04` confirms that call.
  The host remembers its own anchor writes and restores them while the map's
  camera already supplies a 16:9 viewport, avoiding a second inset.
  Live class names identify full-picture exceptions: `Fade_C`, `BattleWipe_C`,
  `Flashback_C`, `EventBackGroundFade_C`, and `WBP_LetterBox_C`.
  `BalloonBundleWidgetBP_C` instead retains a full-width canvas translated left
  by half the extra width. Its projected speaker coordinates otherwise retain
  an extra side margin (300 output pixels at 2520x1080). The translation is
  normalized by viewport width and was verified against two speakers in the
  opening tavern scene; it does not scale dialogue text.
- The camera owner's class `BP_3DWorldMapActorV2_C` retains its authored
  projection so the character-selection map and its picking coordinates agree.
  Names are decoded from the build's FName pool, as shown by `FName::ToString`
  at `0xd936a0`/`0xd93754`.

The concept of correcting both camera aspect and FOV was cross-checked against
[Lyall's Octopath2Fix PC source](https://github.com/Lyall/Octopath2Fix/blob/master/src/dllmain.cpp).
The Switch addresses and ARM64 hook above were independently derived; PC machine
code and addresses are not used.

## Validation and limits

```sh
make -C dm/host/tests GAME=0100A3501946E000 widescreen
.venv/bin/python -m unittest discover -s dm/tools/tests -p test_patches.py
clang -fobjc-arc -Wno-deprecated-declarations -framework Foundation \
  dm/ios/Sources/DisplayConfig.m dm/ios/tests/t_display_config.m \
  -o /tmp/t_display_config
/tmp/t_display_config /tmp/display-test.pak
python3 scripts/test_ios_display.py --udid SIMULATOR_UDID --work /tmp/ot2-display-check
```

The display harness uses the actual iOS front end with synthetic game services.
It reports window/view/drawable geometry in `Documents/checks.json`, loads no
game code, and marks a ratio change after launch as requiring a restart.
It is not a full-game Simulator port.

Camera tests cover both aspect directions, invalid inputs, build gating,
non-accumulating FOV, map transitions, and fade/dialogue anchors. Display tests
cover the pixel budget, preset selection, invalid modes, and pak generation;
the pak is also readable with the independent Python `uepak.Pak` reader.

Manual checks on 2026-10-30 reached Agnea's opening on Mac at 21:9 and at an
approximately 1.42:1 ratio. Added world content and dialogue alignment were
visually checked. A short 21:9 sample averaged about 59.66 fps. On the physical
Duo, Auto/60 reached Hikari's opening battle; updating LiveContainer removed
the container-related black borders reported during earlier testing.

Full-game UI and cinematic composition are not exhaustively verified. An
intermittent guest allocation abort also occurred in earlier baseline/30 fps
runs and on the phone; this adaptation does not claim to fix it. Native-preset
performance and long-session stability are not established by the short tests.
