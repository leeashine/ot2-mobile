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

The profile requests a 3 GiB UE virtual address space with a 6 GiB alias region and a 6.625 GiB explicit guest reservation. In the same-host/6-GiB-alias comparison, 2 GiB reached Agnea's confirmation but hit a guest Break during scene allocation (`main+0xbd4a84` through `main+0xbd5518`). The 3 GiB sample ran for 300 seconds without Break, but its scene screenshot was entirely purple; this is not proof of playable gameplay. The kernel `phys_footprint` peak was 2,843 MiB. This is a macOS experiment, not evidence that the layout or footprint is valid on iPhone.

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

## Known gaps

- The uniform-purple failure is resolved in the observed tavern scene, but blur and 102 newly observed missing-map keys remain in the longer sample.
- Unmatched/general geometry shaders are still unsupported; only the metadata-verified slice operation is folded into the vertex stage.
