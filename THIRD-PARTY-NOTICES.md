# Third-party notices

## Optional d2r-mobile / Route-A classic-Metal NVN backend (MIT)

The optional `M3_GFX_DIR` build mode combines an external Route-A NVN object
layer with the vendored `dm/host/m3_routea_nvn_mtl.m` classic-Metal replay
backend. That file derives from `d2r-mobile/dm/gfx/nvn/nvn_mtl.m` at commit
`9393b00ea9aca52d9254214da93738f26582562f`, through
`ot2-ios-route-a/host/nvn_hle/nvn/nvn_mtl.m` at commit `60a7f0bc213e`.
The remaining external `nvn/` and `tex/` files carry per-file source
annotations. This trial selects that Route-A tree because it contains locally
verified Octopath Traveler II object-layout fixes; nxnative's host, rewriter,
profile handling and offline shader pipeline remain in use.

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
