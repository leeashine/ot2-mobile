// Synthetic camera/widget/rectangle fixtures; no game assets or executable bytes.
#include "../hle_widescreen.c"
#include <assert.h>
#include <sys/mman.h>

module_t g_mod[MAX_MOD];
int g_nmod = 1;
module_t *module_of(const void *p) { (void)p; return NULL; }
void dm_guest_write_prepare(void *p, size_t n) { assert(p && n); }
static void (*callbacks[OBS_MAX])(const uint64_t *);
void gate_obs_set(int id, void (*fn)(const uint64_t *)) { assert(id < OBS_MAX); callbacks[id] = fn; }

int main(void) {
    size_t size = 0x7000000;
    g_mod[0].base = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
    assert(g_mod[0].base != MAP_FAILED);
    strcpy(g_mod[0].name, "main");
    strcpy(g_mod[0].build_id, "65619a04b8a04b10d44f9996ef141062");
    uint8_t view[0x60] = {0}, widget[0x230] = {0};
    uint64_t regs[31] = {0}; regs[19] = (uintptr_t)view;
    float fov = 40, native = 16.0f / 9.0f, got, aspect;
    memcpy(view + 0x18, &fov, 4); memcpy(view + 0x2c, &native, 4);
    unsetenv("DM_CAMERA_ASPECT"); callbacks[OBS_UE_CAMERA](regs);
    memcpy(&got, view + 0x18, 4); assert(got == fov);
    setenv("DM_CAMERA_ASPECT", "2.333333333", 1);
    for (int i = 0; i < 3; i++) {
        memcpy(view + 0x18, &fov, 4); memcpy(view + 0x2c, &native, 4);
        callbacks[OBS_UE_CAMERA](regs);
        memcpy(&got, view + 0x18, 4); memcpy(&aspect, view + 0x2c, 4);
        assert(fabsf(aspect - 7.0f / 3.0f) < 0.00001f);
        assert(fabsf(tanf(got * M_PI / 360) / aspect - tanf(fov * M_PI / 360) / native) < 0.00001f);
    }
    memcpy(view + 0x18, &fov, 4); view[0x31] = 1;
    callbacks[OBS_UE_CAMERA](regs); memcpy(&got, view + 0x18, 4); assert(got == fov);
    view[0x31] = 0; setenv("DM_CAMERA_ASPECT", "nan", 1);
    callbacks[OBS_UE_CAMERA](regs); memcpy(&got, view + 0x18, 4); assert(got == fov);
    setenv("DM_CAMERA_ASPECT", "2.333333333", 1); g_mod[0].build_id[0] = '0';
    callbacks[OBS_UE_CAMERA](regs); memcpy(&got, view + 0x18, 4); assert(got == fov);
    g_mod[0].build_id[0] = '6';
    // A square-ish foldable preserves horizontal content and adds vertical view.
    setenv("DM_CAMERA_ASPECT", "1.4215246637", 1);
    memcpy(view + 0x18, &fov, 4); memcpy(view + 0x2c, &native, 4);
    callbacks[OBS_UE_CAMERA](regs);
    memcpy(&got, view + 0x18, 4); memcpy(&aspect, view + 0x2c, 4);
    assert(got == fov && aspect < native);
    assert(tanf(got * M_PI / 360) / aspect > tanf(fov * M_PI / 360) / native);

    setenv("DM_HUD_ASPECT", "2.333333333", 1);
    float anchors[4] = {0, 0, 1, 1}; memcpy(widget + 0x210, anchors, sizeof anchors);
    regs[0] = (uintptr_t)widget; callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    memcpy(anchors, widget + 0x210, sizeof anchors);
    assert(fabsf(anchors[0] - 300.0f / 2520) < 0.00001f);
    assert(anchors[1] == 0 && anchors[3] == 1 && fabsf(anchors[2] - (1 - anchors[0])) < 0.00001f);
    callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    assert(!memcmp(anchors, widget + 0x210, sizeof anchors));
    map_view = 1; callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    float native_anchors[4] = {0, 0, 1, 1};
    assert(!memcmp(native_anchors, widget + 0x210, sizeof anchors));
    map_view = 0; callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    assert(!memcmp(anchors, widget + 0x210, sizeof anchors));
    uintptr_t block = (uintptr_t)g_mod[0].base + 0x1000;
    memcpy(g_mod[0].base + 0x6f040c0 + 0x28, &block, 8);
    const char *full[] = {"Fade_C", "BalloonBundleWidgetBP_C", "BattleWipe_C"};
    for (unsigned i = 0; i < 3; i++) {
        uintptr_t klass = (uintptr_t)g_mod[0].base + 0x2000 + i * 0x100;
        uint32_t index = 128 + i * 32; uint16_t head = (uint16_t)(strlen(full[i]) << 6);
        memcpy((void *)(klass + 0x18), &index, 4);
        memcpy((void *)(block + index * 2), &head, 2);
        memcpy((void *)(block + index * 2 + 2), full[i], strlen(full[i]));
        memcpy(widget + 0x10, &klass, 8);
        callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
        if (i == 1) {
            float shifted[4]; memcpy(shifted, widget + 0x210, sizeof shifted);
            assert(fabsf(shifted[0] + 300.0f / 2520) < 0.00001f);
            assert(fabsf(shifted[2] - shifted[0] - 1) < 0.00001f);
        } else assert(!memcmp(native_anchors, widget + 0x210, sizeof anchors));
    }
    setenv("DM_HUD_ASPECT", "1.4215246637", 1);
    memset(widget + 0x10, 0, 8);
    memcpy(widget + 0x210, native_anchors, sizeof anchors);
    callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    memcpy(anchors, widget + 0x210, sizeof anchors);
    assert(anchors[0] == 0 && anchors[2] == 1);
    assert(anchors[1] > .1f && anchors[1] < .101f);
    assert(fabsf(anchors[3] - (1 - anchors[1])) < .00001f);
    map_view = 1; callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    assert(!memcmp(native_anchors, widget + 0x210, sizeof anchors));
    map_view = 0;
    uintptr_t balloon_class = (uintptr_t)g_mod[0].base + 0x2100;
    memcpy(widget + 0x10, &balloon_class, 8);
    callbacks[OBS_UE_VIEWPORT_ANCHORS](regs);
    assert(!memcmp(native_anchors, widget + 0x210, sizeof anchors));
    munmap(g_mod[0].base, size);
    puts("PASS: Hor+/Vert+ projection, invalid views, and HUD/fade/dialogue anchors");
}
