# Octopath Traveler II macOS trial

## Scope

This trial combines nxnative's host, UE tooling, offline shader pipeline and profile flow with the classic-Metal (`DM_NVN_M3`) NVN backend derived from d2r-mobile/route-a. It targets macOS 15 and does not change the default backend. The trial is enabled only when `M3_GFX_DIR` is supplied at build time and `OT2_NVN_HLE=1` is supplied at run time.

No game files, rewritten modules, raw shader bytes, shader libraries, keys, logs or screenshots belong in this repository. They remain under `~/local-work`.

## UE4 version-11 inline shaders

OT2's version-11 PAK index is not encrypted. It contains `Engine/GlobalShaderCache-SF_GLSL_SWITCH.bin` and inline material shader maps in `.uexp` files instead of standalone `ShaderArchive*.ushaderbytecode` files.

- `uepak.py` now exposes PAK entries that can contain inline shaders.
- `shader_split.py` feeds those entries through the `UE_INLINE` path and handles zlib-compressed PAK records.
- OT2's compact `LSLG` records do not use the legacy inline layout, so static extraction alone is not yet complete.
- `nvn_capture_split.py` is the local-only fallback: it converts runtime NVN captures into the ordinary offline package/map/facts/pairs inputs. Raw captures and generated shader bytes remain outside the repository.

The observed local set contains 1,612 unique programs: 686 compute, 3 geometry, 838 pixel and 85 vertex programs. The offline build compiled 1,580 programs and reused 44 cached outputs; 38 variants were generated.

## Classic-Metal texture-slot compatibility

The classic recorder stores a separate texture bound at logical slot `r` in `S.tex[stage][r]`. Route-B reflection names the same hardware `c2` binding as slot `128 + r`. Looking up the reflection slot directly therefore rejected every OT2 sampled texture and bound the dummy texture (`tid=0`), including the final composite pass.

`m3_routea_nvn_mtl.m` translates reflection slots `128..255` back to recorder slots `0..127` at lookup. This does not alter combined texture/sampler bindings or guest state. After the change, the final 1280×720 composite input resolved to a real texture instead of the dummy texture.

## Observed result

A macOS run using offline shaders produced real game pixels through Metal:

- frame 180: 1920×1080 loading screen with a bottom-right badge, SHA-256 `aecc309b44d0cc75f8bf8d46debac80ea1324cc31f70672051621d23a739a6a9`;
- frame 300: 1920×1080 brightness/settings screen with two complete HD-2D preview images, SHA-256 `bedf35c62dc76b535538c77dded90da25e9a64189e0fa63bc0206c9fc0dcd3cc`.

The screenshots are kept only in `~/local-work/route-a-frames/`. This proves the hybrid path can execute OT2's real command flow and produce a visible Metal frame; it does not establish rendering correctness or playability.

## UI and input follow-up

`m3_routea_nvn_refl.m` normalizes separate texture reflection slots before facts-driven linking. UI text is now visible, including the settings page, title menu, traveler selection and Agnea's introduction. Scripted/interactive `DM_KEYS` and `DM_CTL` input has reached the adventure confirmation and story text. Screenshots remain local; scene loading previously ended in a guest Break as application-pool usage approached its limit.

## OT2 allocator replacement

For main build `65619a04b8a04b10d44f9996ef141062`, `GCreateMalloc` allocates the object and calls the FMallocBinned3 constructor at main+`0xbd4348`. That constructor reserves `0x940000000` bytes (37 GiB). The OT2 `patches.py` skips only that call; observation gate 21 at main+`0xbd434c` installs the existing host malloc-zone vtable before the object is published.

The relocated guest table at main+`0x642c048` has 20 entries. Its allocation/free slots match the existing UE4 ABI, but it has no slot 20 (`OnMallocInitialized`). The host preserves trivial guest methods and replaces allocation, size, TLS-cache and allocator-stat dumping methods as for the other supported UE profiles. A synthetic test checks aligned allocation, realloc content preservation, usable size and balanced release without using game bytes.

The original experiments used a 3 GiB UE virtual address space with a 6 GiB alias region and a 6.625 GiB explicit guest reservation; the current approved profile uses the smaller tested 5 GiB alias / 5.625 GiB reservation below, with UE VA unchanged. In the same-host/6-GiB-alias comparison, 2 GiB reached Agnea's confirmation but hit a guest Break during scene allocation (`main+0xbd4a84` through `main+0xbd5518`). The 3 GiB sample ran for 300 seconds without Break, but its scene screenshot was entirely purple; this is not proof of playable gameplay. The kernel `phys_footprint` peak was 2,843 MiB. This is a macOS experiment, not evidence that the layout or footprint is valid on iPhone.

## Integer fragment outputs

The old classic-Metal backend always selected the default floating-point fragment entry. The local cache already contains `entry_u` metadata and `main0_u` functions, but rendering an integer attachment such as `R16Uint` still used `float4`, which Metal rejected.

The entry loading, all-uint/mixed-uint render-target selection, integer blending rules and failed-pipeline facts hint are ported from nxnative `0f99c353d3abc334c39855d691afdfab40f4639f`. The external classic `nvn_refl` ABI is unchanged: whether the color-output mask is known is stored on `NvShader`. Existing explicit diagnostic fragment overrides keep precedence.

The post-port 300-second run had zero `R16Uint` pipeline errors and zero guest Breaks, but still presented uniform purple. Its sampled peak RSS was 2,670.1 MiB (295 samples at approximately one second), and peak kernel `phys_footprint` was 2,777 MiB. The acceptance criterion “non-purple scene” is therefore **not met**.

At diagnostic frame 2400, 42 color targets were registered for dumping. The first purple target in the observed post-processing chain was serial 15055, pass 182402, fragment key `8dc677a6f9e3de9f_b`; its scene-color input 15052 was dark but not purple. This pass also sampled a 32³ LUT (serial 1759) written by pass 182401 (`a7aa2c119e1ea39f_b`). Subsequent targets 15056/15057/15058 propagated purple into the present target. At that checkpoint the LUT producer's vertex metadata (`25dadade83d69970_b`) supplied `entry_layer=main0_l`, and the geometry metadata (`439bed623be839b2_b`) supplied `gs_slice`, but the classic loader did not select those layer entries.

## Slice geometry and layered LUT follow-up

The slice-geometry fold and layered render-pass setup are ported from nxnative `0f99c353d3abc334c39855d691afdfab40f4639f`. Only matching `gs_slice`/`layer_from` metadata with an available layer-writing vertex entry is accepted; unresolved geometry remains fail-closed. This does not implement a general geometry-shader backend.

The 180-second local run `lut-layer-trial` selected the layer entry and rendered 32 layers, with no load failure for `439bed623be839b2_b`, no `R16Uint` pipeline error and no guest Break. The 32×32×32 RGB10A2 LUT readback contained nonzero data in every layer and 32 distinct per-layer SHA-256 values. Its 131,072-byte payload SHA-256 was `eb0a9894825697c54349347b6c4a482c8faf31f4df1c68563f6814d035058c35`.

The final scene remained uniformly purple, but the failure boundary moved: frame 2400 tone-map output 15054 and following post-process output 15055 were no longer uniformly purple. Targets 15056/15057 were pure magenta, and their passes 182088/182089 recorded no write; final pass 182090 sampled 15057. The run also logged 95 distinct missing offline shader-map keys. At that checkpoint no particular missing key had been causally assigned to those two unwritten targets.

The run used an external gfx snapshot pinned to Route-A commit `daff9d0d3be6a8c388c137dbc52a3baf2ce029dd`, not its concurrently edited working tree. The 4,697 uninitialized-FenceSync warnings remained: that branch skips sync binding rather than writing color, but an indirect resource-lifetime/order effect is not excluded. No fence behavior was changed.

### Post-processing draw diagnosis

A follow-up run reused the same binary with `DM_NVN_DRAWTRACE=1`. The two equivalent post-processing positions were numbered 15040/15041 in that run. Each had one draw, both with `pso=missing-vs`, `result=pipeline-unavailable` and zero encoded Metal draws; their vertex and fragment stages were absent, rather than rejected by the Metal compiler.

| Position | Vertex lookup key | Fragment lookup key |
|---|---|---|
| First unwritten post-process target | `ad4856161a08096b` | `6bb30e3cbfeb5ef2` |
| Second unwritten post-process target | `b09c0440d883a6a0` | `c6f312852de690d6` |

All four keys also occurred in the previous run's missing-map list, and the active cache contained no corresponding `<key>_b` library. The local `lut-drawtrace-trial/missing-postprocess-shaders.tsv` records capture stems, lengths and SHA-256 values for the shader track; raw data stays outside the repository. This identifies the skipped writes, not a completed rendering fix.

### Runtime-capture rebuild acceptance

Processing the complete local pending directory produced 1,712 unique shaders, covering all previous 1,612 and the four missing post-process keys; 10,250 capture records were rejected by the existing validity checks. With `DOTNET_ROOT` set to the installed runtime, `dmsh_build.py` built 1,712/1,712 successfully into the private `cache-a/b-e83a95ef084e`, without symlinks or tool-source changes. The package and replacement profile tables live only under `~/local-work/nx/runtime-capture-all/`.

Reusing the same 3-GiB host, the matched frame-2400 diagnostic window had zero missing-map keys versus 95 before. Both repaired programs had a cache-hit PSO and one encoded Metal draw; their targets, numbered 15052/15053 in that run, were recorded as written. A subsequent 240-second story-progression run reached a non-purple tavern scene with visible people, flames and dialogue (local screenshot `run-79539-frame-006900.png`). The picture remains visibly blurred, and the longer run exposed 102 new missing-map keys: this is not a claim of complete rendering or full-session map coverage.

### Depth-convention correction

OT2 selects NVN near=0 depth, but the classic loader had always selected `main0`, whose translated vertex output applies the GL conversion `z/2+w/2`. The local object-layer snapshot now forwards DeviceSetDepthMode to the replay layer; ordinary vertex loads select `entry_z` and slice loads select `entry_layer_z`. Function-constant specialization uses the same selected entry. Missing entries are reported, and a mode change after vertex loading is reported rather than silently treated as supported.

The same-input 300-second run logged `main0_z` and `main0_lz` before rendering, without a late-mode warning. The previous Agnea dialogue window was uniformly blurred; `run-52533-frame-008820.png` instead shows distinguishable characters, stage, lamps, tables and floor. The title sample `run-52533-frame-000900.png` still shows selective background blur. No DOF pass was disabled. This supports the depth-convention mismatch as the cause of the observed whole-screen blur, not a claim of full rendering correctness or playability. Host unit tests passed; the run had no Break and one newly observed missing shader key, `b9f763a3db71dfd4`.

### Agnea controls and longer clear-scene samples

The approved depth/object snapshot is archived locally as `625903f` (no push). With the same binary, the 600-second and 380-second samples both exited gracefully without a guest Break. In the latter, `B` closes Basic Controls, left/down stick inputs change Agnea's position relative to the stage and stationary NPCs, and `X` opens the actual main menu. Local frames `run-20459-frame-008880.png`, `009120.png`, `009360.png` and `009600.png` show the sequence. Continuous scripted `A` had previously reopened Inventory; that was input interference, not movement evidence.

The 500 presented-frame samples 9000–9499 averaged 29.957 FPS in both runs, with 95th-percentile frame times of 34.158/34.171 ms. This is paced presentation, not an uncapped GPU benchmark. Sampled RSS peaks were 2,901.6/2,846.1 MiB; kernel `phys_footprint` peaks were 3,004/3,017 MiB. The tested state is the tavern objective “Collect tips from the tavern patrons”, not combat or new-area exploration.

The runs exposed 21/17 distinct missing-map keys. All are covered by a new private capture package of 1,835 shaders; 1,835/1,835 built successfully on the unchanged `e83a95ef084e` chain, including 21 newly compiled Metal libraries. Its tables/cache are separate from the online runs (`runtime-capture-play/`, `ot2-shaders/cache-a-play/`), so those runs do not prove zero remaining misses after the rebuild.

A local-only AudioUnit callback probe measured the PCM16 already produced by the game's output, without retaining raw samples. In the 55-second title smoke, output 0 at callback 4000 had 1,024/1,024 nonzero samples and peak amplitude 5,529/32,768; output 1 remained zero at those sampled callbacks. This proves nonzero game audio reaches the CoreAudio callback, not subjective listening quality or complete voice/effect support. An earlier probe forwarding method stalled AudioUnit initialization; that sample is excluded. The corrected probe reached the visible title screen and exited normally. The same smoke loaded all 1,835 map entries with zero missing-map warnings, but did not exercise every newly built shader.

### Smaller reservation experiment (UE VA remains 3072 MiB)

| Alias / explicit reserve | Observed result |
|---|---|
| 4.375 / 5 GiB (`0x118000000` / `0x140000000`) | SDK `AllocateAddressRegion` returned `ResultOutOfVirtualAddressSpace` for the 3 GiB UE request; guest Break before the first frame. |
| 5 / 5.625 GiB (`0x140000000` / `0x168000000`) | Private-header build reached tavern dialogue, control HUD and 11,160 presents; 376 seconds wall time, graceful exit 0. |
| 5.5 / 6.125 GiB | Privately compiled but not run; the smaller tested case already passed. |

The smallest **tested passing** alias is 5 GiB; values between 4.375 and 5 GiB are untested. The passing sample's RSS peak was 2,673.6 MiB and kernel footprint peak was 3,173 MiB. Concurrent compilation, compression and differing run lengths prevent a causal physical-memory comparison. These are macOS results, not iPhone entitlement or memory-limit evidence. Following explicit approval, `game.tsv` now adopts `mem_reserve=0x168000000` and `mem_alias=0x140000000`, retaining `-SwitchVirtualAddressSpaceSize=3072`. The failed 4.375-GiB target remains recorded above; private comparison evidence stays under `small-va-trial/va-a5/`.

### Diagnostic disk limits

Before and during future runs, keep available disk above 9 GiB; do not start, or stop owned game processes, at or below that threshold. Disable periodic frame capture (`OT2_NVN_CAPTURE_EVERY=0`); use at most 16 explicit `DM_NVN_SHOT` frames and at most four manual shots per run. Keep key evidence, compress completed large logs, and remove completed private `temp/` directories without touching saves, shared caches or other sessions' files.

## Known gaps

- The observed uniform-purple and whole-screen-blur failures are resolved, and movement/main-menu input is verified in the tavern. Combat, extended exploration, full rendering correctness and rebuilt-cache coverage in later scenes remain unverified.
- Unmatched/general geometry shaders are still unsupported; only the metadata-verified slice operation is folded into the vertex stage.

## Before open-source release

- Replace the inherited `$HOME/local-work` shader-capture destination in `m3_routea_hle_nvn.c` and `NSHomeDirectory()` diagnostic destinations in `m3_routea_nvn_mtl.m` with explicit environment-variable paths; when unset, disable diagnostic writes. These are known legacy runtime paths, not bundled game assets, and do not block this local milestone.
