// Synthetic host metadata; no guest binary or captured commands.
#include "../m3_routea_hle_nvn.c"
const tex_t *test_retire_texture_snapshot(int descriptor) {
    NVNtexture texture = {0};
    tex_t *t = TX(&texture);
    t->magic = MAGIC('T', 'E', 'X', 0); t->serial = nvn_new_serial();
    if (descriptor >= 0) { mtl_reg_tex(descriptor, t, NULL); mtl_reg_tex(descriptor + 1, t, NULL); }
    const tex_t *copy = snap_tex(&texture);
    h_nvnTextureFinalize(&texture);
    return copy;
}
void test_reap_texture_snapshots(uint64_t completed_submit) { snap_tick(completed_submit); }
