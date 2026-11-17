# OT2 1.1.1 selectable frame-rate test

The launcher exposes **Frame rate: 30 fps / 60 fps**, defaulting to 30.
Choose before starting the game; exit and relaunch to change it. On the Mac,
the rebuilt host accepts `DM_FPS_TARGET=30` or `DM_FPS_TARGET=60`.
The existing frame-rate counter is enabled in the exported test IPA.

## Implementation

The classic-Metal NVN present path now calls the existing engine-limit helper,
as the other NVN backend does. Only main build
`65619a04b8a04b10d44f9996ef141062` receives the OT2 writes:

| Variable | TAutoConsoleVariable offset | Value-pointer offset | 30 / 60 settings |
| --- | --- | --- | --- |
| `t.MaxFPS` | `0x76b7f58` | object + `0x10` | 30 / 60, float |
| `rhi.SyncInterval` | `0x75660d0` | object + `0x10` | 2 / 1, int32 |

Both game-thread and render-thread copies are updated. The registration
functions were identified by UTF-16 name references and checked in the
user-supplied executable: references at `0x2e37e4c` / `0x1334ac4`, value-pointer
stores at `0x2e37e88` / `0x1334afc`. The game's Switch device profile sets 30
and 2. Logs confirm the 60 target changes both copies, including after the
game reapplies its settings. No guest clock or animation multiplier changes.

## Mac validation, 2026-10-30

Built the classic-Metal host and ran the user's 1.1.1 game with offline shaders,
separate test saves and scripted pad input. These are headless Metal renders,
not an iPhone performance measurement; audio was not enabled.

- 30 target: a stable 600-present sample averaged 29.96 fps, median 33.378 ms.
- 60 target: a stable 600-present tavern sample averaged 59.82 fps, median
  16.720 ms (presents 28537–29136).
- 60 passed initial settings, title, character selection, Agnea's opening
  scenes/dialogue, basic-controls tutorial and a movement input in the tavern.
- The fresh 30 run also reached the tutorial. From the same initial tavern
  position, both modes received 0.5 seconds down, then 0.5 seconds right.
  The resulting rightward movement and camera displacement were visually
  comparable (within a few pixels), with no doubled movement speed observed.
- One initial 30 run exited in the RenderThread with a guest allocation
  failure (`main+0xc16c30`, whose diagnostic is "Ran out of memory allocating").
  A fresh 30 run passed the same scene load. The cause is unresolved; do not
  describe this build as a stability fix.

Frame-rate selection and this short movement comparison are verified. Timing throughout the game and long-session stability remain unverified.

## Launcher interaction

The full-screen launcher has no navigation stack. Two-option choices use an
explicit segmented picker; longer lists use a menu. This avoids relying on
SwiftUI's automatic navigation-based presentation and made the frame-rate
control usable in the tested LiveContainer setup. Env-file overrides remain
locked and are labeled as such.

An isolated simulator test using the actual `Launcher.swift` selected 60,
pressed Play, checked `DM_FPS_TARGET=60`, relaunched to verify persistence,
then selected 30 and checked the applied value. The full game was subsequently
observed near 60 fps in the phone's opening scene/battle. These checks do not
establish sustained performance or stability across the whole game.

See [iPhone Duo adaptation](ot2-widescreen-test.md) for the unsigned IPA exporter
and automatic display settings. No game assets or generated binaries are stored
in this repository.
