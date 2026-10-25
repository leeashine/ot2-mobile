// Replay/retirement ordering against the real cache and a tiny Metal texture.
#include "../m3_routea_nvn_mtl.m"
#include <assert.h>
#include "t_m3_runtime_stubs.h"
extern const tex_t *test_retire_texture_snapshot(int);
extern void test_reap_texture_snapshots(uint64_t);
int main(void) { @autoreleasepool {
    g_dev = MTLCreateSystemDefaultDevice(); assert(g_dev);
    const tex_t *snapshot = test_retire_texture_snapshot(-1);
    uint64_t serial = snapshot->serial;
    MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:2 height:2 mipmapped:NO];
    id<MTLTexture> resource = [g_dev newTextureWithDescriptor:d]; assert(resource);
    // CPU Finalize ran before this already-recorded command reached replay.
    serial_put(serial, resource); resource = nil;
    assert(g_by_serial.n == 1);
    const tex_t *registered = test_retire_texture_snapshot(3);
    uint64_t registered_serial = registered->serial;
    resource = [g_dev newTextureWithDescriptor:d]; assert(resource);
    serial_put(registered_serial, resource); resource = nil;
    test_reap_texture_snapshots(7);
    assert(g_by_serial.n == 2 && "queued references must survive the grace period");
    test_reap_texture_snapshots(8);
    assert(!serial_get(serial) && "retired snapshots must not orphan a cache created after CPU Finalize");
    assert(serial_get(registered_serial) && "descriptors outlive the CPU texture object");
    mtl_reg_tex(3, NULL, NULL);
    assert(serial_get(registered_serial) && "another descriptor still owns the texture");
    mtl_reg_tex(4, NULL, NULL);
    assert(g_by_serial.n == 0 && "the last descriptor releases a retired texture");
    tex_t live = {.magic = MAGIC('T', 'E', 'X', 0), .serial = nvn_new_serial()};
    resource = [g_dev newTextureWithDescriptor:d]; assert(resource);
    serial_put(live.serial, resource); resource = nil;
    mtl_reg_tex(5, &live, NULL); mtl_reg_tex(5, NULL, NULL);
    assert(serial_get(live.serial) && "a live CPU texture must keep its rendered contents");
    mtl_tex_release(&live);
    assert(g_by_serial.n == 0);
    assert(g_texture_retired.n == 0 && g_texture_descriptor_refs.n == 0);
    g_done = UINT64_MAX; defer_drain();
    assert(g_deferred.count == 0);
    puts("PASS: queued texture replay cannot retain a finalized texture indefinitely");
} }
