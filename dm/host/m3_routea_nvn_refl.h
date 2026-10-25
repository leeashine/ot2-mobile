// Source: d2r-mobile/dm/gfx/nvn/nvn_refl.h;
// commit 9393b00ea9aca52d9254214da93738f26582562f.
// Copyright (c) 2026 jhaizhou. MIT; see LICENSE and THIRD-PARTY-NOTICES.md.
// Keep the classic replay ABI, including inline c1 storage. Only the binding
// and argument-slot capacities are raised; the current gfx header owns c1
// dynamically and is not layout-compatible with this parser/replay pair.
#pragma once
#include <stdint.h>

enum { NVN_RB_CBUF = 1, NVN_RB_SAMP, NVN_RB_TEX, NVN_RB_IMG, NVN_RB_TBUF,
       NVN_RB_SBUFP, NVN_RB_SUPPORT, NVN_RB_C1, NVN_RB_DRV0, NVN_RB_DRV2,
       NVN_RB_SAMPT, NVN_RB_UBOP };
enum { NVN_DPF_FLOAT = 0, NVN_DPF_UINT, NVN_DPF_SINT, NVN_DPF_DEPTH };
enum { NVN_CT_FLOAT = 0, NVN_CT_UINT, NVN_CT_INT };
#define NVN_REFL_MAXARG 192
#define NVN_REFL_MAXB NVN_REFL_MAXARG
#define NVN_REFL_MAXV 32

typedef struct {
    uint8_t kind, rw;
    uint8_t dtt, dpf;
    uint16_t reg, aid;
} nvn_rbind;
typedef struct {
    int nb, abi, nv;
    nvn_rbind b[NVN_REFL_MAXB];
    struct { uint8_t loc, ct, nvn; } v[NVN_REFL_MAXV];
    uint16_t tg[3];
    uint8_t route_b, has_c1;
    uint8_t drv_read[3];
    uint16_t c1_len;
    int8_t pos_attr;
    uint8_t pos_w1, may_discard, writes_smask, color_mask;
    uint8_t nfc, fc_reg[32], fc_locn[32], nfo, fo_color[4];
    uint64_t fc_mixed[2];
    int8_t uv_attr[32];
    int8_t uv_aff_attr[32];
    uint16_t uv_aff[32][4];
    uint8_t c1[4096];
} nvn_refl;

#ifdef __OBJC__
#import <Foundation/Foundation.h>
int nvn_refl_from_json(NSDictionary *j, nvn_refl *out, char *err, int errlen);
#endif
