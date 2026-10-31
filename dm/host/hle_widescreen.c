// Opt-in Hor+/Vert+ projection at a build-verified UCameraComponent::GetCameraView
// gate. Change the freshly produced view, never the persistent camera component:
// animated FOV is preserved and the correction cannot accumulate across frames.
#include "hle.h"
#include <math.h>
#include <mach/mach.h>

static uint8_t *wide_main(void) {
    for (int i = 0; i < g_nmod; i++)
        if (!strcmp(g_mod[i].name, "main") && !strcmp(g_mod[i].build_id, "65619a04b8a04b10d44f9996ef141062")) return g_mod[i].base;
    return NULL;
}
static int wide_read(uintptr_t address, void *out, size_t count) {
    vm_size_t got = 0;
    return address >= 0x1000 && vm_read_overwrite(mach_task_self(), address, count, (vm_address_t)out, &got) == KERN_SUCCESS && got == count;
}
// FName::ToString at main+d936a0 / d93754: pool at +6f040c0,
// block pointers at +28, 16-bit entry offsets in two-byte units, length >> 6.
static void wide_object_name(uintptr_t object, char out[128]) {
    out[0] = 0;
    uint8_t *base = wide_main(); uint32_t index; uintptr_t block; uint16_t head;
    if (!base || !wide_read(object + 0x18, &index, 4) ||
        !wide_read((uintptr_t)base + 0x6f040c0 + 0x28 + ((index >> 16) * 8ull), &block, 8)) return;
    uintptr_t entry = block + (index & 0xffff) * 2;
    if (!wide_read(entry, &head, 2)) return;
    unsigned n = head >> 6; if (n > 127) n = 127;
    if (head & 1) {
        uint16_t text[127]; if (!wide_read(entry + 2, text, n * 2)) return;
        for (unsigned i = 0; i < n; i++) out[i] = text[i] < 128 ? text[i] : '?';
    } else if (!wide_read(entry + 2, out, n)) { out[0] = 0; return; }
    out[n] = 0;
}
static int wide_map_camera(uintptr_t camera) {
    // The 3D map is a fixed 16:9 UI, including its picking coordinates. Keep its
    // projection authored, while exploration/cinematic cameras use Hor+.
    uintptr_t outer = 0, klass = 0;
    if (!wide_read(camera + 0x20, &outer, 8) || !wide_read(outer + 0x10, &klass, 8)) return 0;
    static uintptr_t cached_class; static int cached_map;
    if (klass != cached_class) {
        char name[128]; wide_object_name(klass, name);
        cached_class = klass; cached_map = !strcmp(name, "BP_3DWorldMapActorV2_C");
        if (cached_map) LOG("wide camera: retaining authored projection for the 3D world map");
    }
    return cached_map;
}

static int map_view;

static void camera_view(const uint64_t *regs) {
    static int logged, invalid_logged;
    // Read at use so DM_CTL's existing "env" command can compare two
    // projections at the same stationary gameplay position without restarting.
    const char *e = getenv("DM_CAMERA_ASPECT");
    if (!e || !*e) return;
    char *end;
    float aspect = strtof(e, &end);
    if (!*end && aspect == 0) return;
    if (*end || !isfinite(aspect) || aspect < 1.0f || aspect > 3.6f) {
        if (!invalid_logged) {
            invalid_logged = 1;
            LOG("[RED] DM_CAMERA_ASPECT must be a number from 1 to 3.6");
        }
        return;
    }
    if (strcmp(dm_main_build(), "65619a04b8a04b10d44f9996ef141062")) return;
    map_view = wide_map_camera(regs[20]);
    if (map_view) return;
    uint8_t *view = (uint8_t *)(uintptr_t)regs[19];
    if (view[0x31]) return; // Orthographic projection requires a separate policy.
    float fov, old_aspect;
    memcpy(&fov, view + 0x18, sizeof fov);
    memcpy(&old_aspect, view + 0x2c, sizeof old_aspect);
    if (!isfinite(fov) || fov <= 1 || fov >= 175 ||
        !isfinite(old_aspect) || old_aspect < 1 || old_aspect > 3.6f) return;
    // Preserve the authored view: wider displays add horizontal world;
    // narrower displays keep horizontal FOV and reveal more vertically.
    float wide_fov = aspect > old_aspect ?
        2.0f * atanf(tanf(fov * (float)M_PI / 360.0f) * aspect / old_aspect) * 180.0f / (float)M_PI : fov;
    dm_guest_write_prepare(view + 0x18, 0x18);
    memcpy(view + 0x18, &wide_fov, sizeof wide_fov);
    memcpy(view + 0x2c, &aspect, sizeof aspect);
    if (!logged) { logged = 1; LOG("camera expanded view: aspect %g -> %g, horizontal FOV %g -> %g (%s)", old_aspect, aspect, fov, wide_fov, aspect > old_aspect ? "Hor+" : "Vert+"); }
}

__attribute__((constructor)) static void camera_gate(void) {
    gate_obs_set(OBS_UE_CAMERA, camera_view);
}

// Keep full-viewport HUD roots in a centered safe area. Remember only our own
// writes, so a native-aspect map can undo the inset instead of applying it twice.
// Stale entries are never dereferenced: each lookup uses the currently live widget.
static struct { uintptr_t widget; float applied[4]; } anchor_edits[512];
static int wide_widget_layout(uintptr_t widget) {
    uintptr_t klass = 0;
    if (!wide_read(widget + 0x10, &klass, 8) || !klass) return 0;
    static struct { uintptr_t klass; int layout; } types[64]; static unsigned count;
    for (unsigned i = 0; i < count; i++) if (types[i].klass == klass) return types[i].layout;
    char name[128]; wide_object_name(klass, name);
    // Layout 1 covers the full picture. Layout 2 keeps the full canvas size,
    // but removes BalloonBundle's observed extra side margin from its origin.
    // Its vertical speaker coordinates already use the full viewport.
    int full = !strcmp(name, "Fade_C") || !strcmp(name, "BattleWipe_C") ||
        !strcmp(name, "Flashback_C") || !strcmp(name, "EventBackGroundFade_C") ||
        !strcmp(name, "WBP_LetterBox_C");
    int layout = !strcmp(name, "BalloonBundleWidgetBP_C") ? 2 : full;
    if (count < 64) { types[count].klass = klass; types[count++].layout = layout; }
    return layout;
}
static void viewport_anchors(const uint64_t *regs) {
    const char *e = getenv("DM_HUD_ASPECT");
    if (!e || strcmp(dm_main_build(), "65619a04b8a04b10d44f9996ef141062")) return;
    char *end; float aspect = strtof(e, &end);
    if (*end || !isfinite(aspect) || aspect < 1.0f || aspect > 3.6f) return;
    float *anchors = (float *)((uint8_t *)(uintptr_t)regs[0] + 0x210);
    int layout = wide_widget_layout(regs[0]);
    float inset = fmaxf(0, (1 - (16.0f / 9.0f) / aspect) * 0.5f);
    float inset_y = fmaxf(0, (1 - aspect / (16.0f / 9.0f)) * 0.5f);
    float left = map_view || layout == 1 ? 0 : layout == 2 ? -inset : inset;
    float right = map_view || layout == 1 ? 1 : 1 - inset;
    float top = map_view || layout ? 0 : inset_y;
    float bottom = map_view || layout ? 1 : 1 - inset_y;
    int slot = -1, ours = 0;
    for (unsigned i = 0; i < sizeof anchor_edits / sizeof *anchor_edits; i++) {
        if (anchor_edits[i].widget == regs[0]) {
            slot = (int)i;
            ours = !memcmp(anchors, anchor_edits[i].applied, 4 * sizeof *anchors);
            if (!ours) anchor_edits[i].widget = 0; // Game reset it or recycled the object.
            break;
        }
        if (!anchor_edits[i].widget && slot < 0) slot = (int)i;
    }
    if (!ours && (anchors[0] != 0 || anchors[1] != 0 || anchors[2] != 1 || anchors[3] != 1)) return;
    if (slot < 0 || (anchors[0] == left && anchors[1] == top && anchors[2] == right && anchors[3] == bottom)) return;
    dm_guest_write_prepare(anchors, 4 * sizeof *anchors);
    anchors[0] = left; anchors[1] = top; anchors[2] = right; anchors[3] = bottom;
    anchor_edits[slot].widget = left != 0 || top != 0 || right != 1 || bottom != 1 ? regs[0] : 0;
    memcpy(anchor_edits[slot].applied, anchors, 4 * sizeof *anchors);
    static unsigned logs;
    if (logs < 4) { logs++; LOG("HUD anchors: aspect %g, left %g, right %g", aspect, left, right); }
    static int dialogue_logged;
    if (layout == 2 && !dialogue_logged) { dialogue_logged = 1; LOG("dialogue viewport: translated origin by (%g,%g), preserving canvas size", left, top); }
}
__attribute__((constructor)) static void anchors_gate(void) {
    gate_obs_set(OBS_UE_VIEWPORT_ANCHORS, viewport_anchors);
}
