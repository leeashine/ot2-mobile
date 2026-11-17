// Synthetic mappings only: no guest image, assets or captured bytes.
// Exercise the OT2 profile through the real public memory SVC interface.
#include "game_profile.h"
#undef DM_GAME_MEM_MAP_LIMIT
#define DM_GAME_MEM_MAP_LIMIT 1
#include "../hle_svc.c"
#include "../hle_uemalloc.c"
#include <assert.h>

module_t g_mod[MAX_MOD];
int g_nmod;
struct dm_flags g_flag;
int svc_thread(int num, uint64_t *regs) { (void)num; (void)regs; return 0; }
void hlecount_svc(int num) { (void)num; }
void dm_backtrace(uint64_t fp) { (void)fp; }
module_t *module_of(const void *p) { (void)p; return NULL; }
uint64_t dm_entropy64(void) { return 1; }
int thr_limit_used(void) { return 0; }
uint32_t thr_cur_handle(void) { return 0; }
void guest_clock_read_wait(void) {}
uint64_t guest_ns(void) { return 0; }

void gate_obs_set(int id, void (*fn)(const uint64_t *)) { (void)id; (void)fn; }
int gate_obs_present(int id) { (void)id; return 0; }

static uint64_t info(unsigned id) {
    uint64_t r[31] = {0}; r[1] = id;
    svc_dispatch(0x29, r, 0);
    assert(r[0] == 0);
    return r[1];
}
static uint64_t map_call(int svc, uint64_t address, uint64_t bytes) {
    uint64_t r[31] = {address, bytes};
    svc_dispatch(svc, r, 0);
    return r[0];
}
int main(void) {
    g_flag.dbg = 1;
    const uint64_t page = 0x4000;
    uint64_t alias = info(I_AliasAddr), before = info(I_UsedMem);
    uint64_t first = alias + 0x200000;
    assert(map_call(0x2c, first, 2 * page) == 0);
    assert(info(I_UsedMem) == before + 2 * page &&
           "mapped physical pages must contribute to UsedMemory for SDK cache pressure");
    assert(info(I_UsedNonSys) == info(I_UsedMem));
    assert(map_call(0x2c, first, 2 * page) == 0);
    assert(info(I_UsedMem) == before + 2 * page);
    assert(atomic_load(&g_vm_diag.map_requested) == 4 * page);
    assert(atomic_load(&g_vm_diag.map_new) == 2 * page &&
           "repeated maps must not inflate the scene-growth ledger");
    assert(map_call(0x2d, first, page) == 0);
    assert(map_call(0x2d, first, page) == 0);
    assert(info(I_UsedMem) == before + page);
    assert(atomic_load(&g_vm_diag.unmap_requested) == 2 * page);
    assert(atomic_load(&g_vm_diag.unmap_released) == page);

    // Fill the advertised budget without touching the virtual pages. A failed
    // extra map must not consume capacity; releasing cached pages must permit
    // a retry, which is the SDK allocator's pressure/reclaim protocol.
    uint64_t remaining = info(I_TotalMem) - info(I_UsedMem);
    uint64_t large = alias + 0x1000000;
    assert(remaining % page == 0);
    assert(map_call(0x2c, large, remaining) == 0);
    assert(info(I_UsedMem) == info(I_TotalMem));
    assert(map_call(0x2c, first, page) == 0x10801);
    assert(info(I_UsedMem) == info(I_TotalMem));
    assert(map_call(0x2d, large, remaining) == 0);
    assert(map_call(0x2c, first, page) == 0);
    assert(map_call(0x2d, first, 2 * page) == 0);
    assert(info(I_UsedMem) == before);
    assert(atomic_load(&g_vm_diag.map_refused) == 1);
    assert(atomic_load(&g_vm_diag.map_new) == atomic_load(&g_vm_diag.unmap_released) &&
           "overlapping unmaps and budget failures must leave the page ledger balanced");
    puts("PASS: OT2 mapped-page accounting, budget refusal and cache-release retry");
    return 0;
}
