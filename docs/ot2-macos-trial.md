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

## Known gaps

- UI text is missing. The next check is whether the runtime font atlas contains pixels and whether its R8/A8 upload and text shader facts are correct.
- The one observed geometry shader is represented as a slice/layer operation and currently has no standalone Metal library in this classic backend.
- Input-driven title/gameplay screenshots have not yet been captured.
