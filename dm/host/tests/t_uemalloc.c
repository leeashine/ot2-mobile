// Hand-made module/object fixture; no guest image, vtable or captured bytes.
#ifndef HLE_UEMALLOC_SOURCE
#define HLE_UEMALLOC_SOURCE "../hle_uemalloc.c"
#endif
#include HLE_UEMALLOC_SOURCE
#include <assert.h>
#include <sys/mman.h>
module_t g_mod[MAX_MOD];
int g_nmod = 1;
static void (*made)(const uint64_t *);
void gate_obs_set(int id, void (*fn)(const uint64_t *)) { assert(id == OBS_UE_MALLOC); made = fn; }
int gate_obs_present(int id) { return id == OBS_UE_MALLOC; }
int main(void) {
    size_t n = 0x642d000;
    uint8_t *b = mmap(NULL, n, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    assert(b != MAP_FAILED);
    strcpy(g_mod[0].name, "main");
    strcpy(g_mod[0].build_id, "65619a04b8a04b10d44f9996ef141062");
    g_mod[0].base = b;
    *(uint32_t *)(b + 0xbd4348) = 0xd503201f;
    dm_ue_malloc_install();
    assert(made && "OT2 allocator observation must be installed before guest constructors");
    uint64_t regs[31] = {0};
    void *object[2] = {0}; regs[19] = (uintptr_t)object; made(regs);
    void **v = object[0];
    void *(*allocate)(void *, size_t, uint32_t) = v[3];
    void *(*resize)(void *, void *, size_t, uint32_t) = v[5];
    void (*deallocate)(void *, void *) = v[7];
    bool (*size_of)(void *, void *, size_t *) = v[9];
    unsigned char *p = allocate(object, 37, 256);
    assert(p && !((uintptr_t)p & 255)); memset(p, 0x5a, 37);
    p = resize(object, p, 4097, 256);
    assert(p && !((uintptr_t)p & 255));
    for (int i = 0; i < 37; i++) assert(p[i] == 0x5a);
    size_t usable = 0; assert(size_of(object, p, &usable) && usable >= 4097);
    assert(!size_of(object, NULL, &usable));
    deallocate(object, p); deallocate(object, NULL);
    assert(atomic_load(&g_used) == 0);
    munmap(b, n); puts("PASS: OT2 allocator slots preserve alignment, realloc contents and allocation size");
    return 0;
}
