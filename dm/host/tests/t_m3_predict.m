// Future passes must not change the scissor used by the current draw.
#include "../m3_routea_nvn_mtl.m"
#include "t_m3_runtime_stubs.h"

static int check_scissor(int enabled) {
    struct {
        op_hdr first;
        p_scissor small;
        op_hdr second;
        p_scissor tiny;
        op_hdr end;
    } future = {
        .first = {OP_SCISSOR, sizeof(op_hdr) + sizeof(p_scissor)},
        .small = {0, 0, 32, 32},
        .second = {OP_SCISSOR, sizeof(op_hdr) + sizeof(p_scissor)},
        .tiny = {0, 0, 1, 1},
        .end = {OP_END, sizeof(op_hdr)},
    };
    const p_scissor current = {7, 11, 1920, 1080};
    R.sc = current;
    R.has_sc = enabled;
    g_exec_next = (const uint8_t *)&future;
    pso_predict_rest();
    g_exec_next = NULL;
    if (R.has_sc != enabled || R.sc.x != current.x || R.sc.y != current.y ||
        R.sc.w != current.w || R.sc.h != current.h) {
        fprintf(stderr, "FAIL: lookahead changed current scissor (enabled=%d): %d,%d %dx%d enabled=%d\n",
                enabled, R.sc.x, R.sc.y, R.sc.w, R.sc.h, R.has_sc);
        return 1;
    }
    return 0;
}

int main(void) { @autoreleasepool {
    int failed = check_scissor(0) | check_scissor(1);
    if (!failed) puts("PASS: future pass scissors cannot leak into the current draw, enabled or disabled");
    return failed;
} }
