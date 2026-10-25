# Third-party notices

## Optional d2r-mobile / Route-A classic-Metal NVN backend (MIT)

The optional `M3_GFX_DIR` build mode uses a local Route-A NVN object-layer
snapshot (`dm/host/m3_routea_hle_nvn.c`) with the vendored classic-Metal replay
backend `dm/host/m3_routea_nvn_mtl.m`. The replay file derives from
`d2r-mobile/dm/gfx/nvn/nvn_mtl.m` at commit
`9393b00ea9aca52d9254214da93738f26582562f`, through
`ot2-ios-route-a/host/nvn_hle/nvn/nvn_mtl.m` at commit `60a7f0bc213e`.
The remaining external `nvn/` and `tex/` files carry per-file source
annotations. This trial selects that Route-A tree because it contains locally
verified Octopath Traveler II object-layout fixes; nxnative's host, rewriter,
profile handling and offline shader pipeline remain in use.

The integer fragment-output entry loading, render-target-aware selection and
failure hints in `dm/host/m3_routea_nvn_mtl.m` are ported from
`nxnative/dm/gfx/nvn/nvn_mtl.m` at
`0f99c353d3abc334c39855d691afdfab40f4639f` (lines 2914, 3099–3106,
4183–4214, 4232–4233, 4343–4353 and 7602–7610).
Copyright (c) 2026 seedds. These portions use the same MIT license text below
(also preserved in this repository's `LICENSE`), with this copyright notice.

The slice-only geometry-to-vertex-layer folding and layered render-pass setup
in that file are also ported from nxnative at the same commit (lines 2785–2795,
2918, 3034, 3053–3077, 3088–3090, 3165–3183, 4234 and 6921–6924).
Copyright (c) 2026 seedds; MIT. This does not add a general geometry backend.

Depth-convention selection (`entry_z` / `entry_layer_z`, including function
constant specialization) is ported from nxnative at the same commit,
`dm/gfx/nvn/nvn_mtl.m` lines 3040–3048 and 3072–3078, and
`dm/gfx/nvn/hle_nvn.c`'s DeviceSetDepthMode forwarding.
Copyright (c) 2026 seedds; MIT.
`dm/host/m3_routea_hle_nvn.c` vendors the object/interface layer from
`ot2-ios-route-a/host/nvn_hle/nvn/hle_nvn.c` at
`daff9d0d3be6a8c388c137dbc52a3baf2ce029dd`, originally d2r-mobile
`dm/gfx/nvn/hle_nvn.c` at `9393b00ea9aca52d9254214da93738f26582562f`.
Original copyright (c) 2026 jhaizhou; MIT text below applies.

Distributors of this source or a resulting binary must preserve the following
notice.

MIT License

Copyright (c) 2026 jhaizhou

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
