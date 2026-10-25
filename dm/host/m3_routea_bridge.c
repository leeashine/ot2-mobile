// OT2 nxnative trial adapter for the MIT Route-A NVN backend.
// The backend source remains external and read-only during the time-boxed trial;
// this file supplies only host diagnostics that Route-A expects.
#include <stdint.h>

// Route-A uses the Horizon handle only in optional synchronization diagnostics.
// nxnative does not expose that private helper across the graphics boundary.

// nxnative's thread scheduler marks host-side graphics work through this TLS.
// Route-A's older interface does not export it, but the scheduler still needs
// a definition. The first integration keeps it zero; submit/present already
// run on Route-A's dedicated translation thread.
__thread _Atomic int dm_host_work;

// Developer-control hooks present in newer nxnative gfx. They are optional for
// running the game and deliberately fail closed until the M3 backend exposes
// equivalent object registries.
void dm_gfx_passdump_next(long n) { (void)n; }
void dm_gfx_texdump_next(const char *path) { (void)path; }
void dm_gfx_texlist(int target) { (void)target; }
void dm_gfx_texraw(uint64_t serial, const char *path) {
    (void)serial;
    (void)path;
}

// Native-texture movie output is not part of the first-frame path. Returning
// -1 makes the codec path reject it instead of writing through an unknown
// Route-A object layout.
int nvn_host_write_texture(const void *texture, const void *source,
                           int width, int height, unsigned long row_bytes,
                           int *texture_width, int *texture_height) {
    (void)texture; (void)source; (void)width; (void)height; (void)row_bytes;
    (void)texture_width; (void)texture_height;
    return -1;
}
int nvn_host_signal_sync(void *sync) {
    (void)sync;
    return -1;
}
uint32_t ot2_gthread_current_handle(void) { return 0; }
