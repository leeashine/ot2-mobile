// Synthetic shader bytes only. Exercise the real composition cache without a GPU.
#include "../m3_routea_nvn_mtl.m"
#include <assert.h>
uint64_t nvn_new_serial(void) { static uint64_t next = 1000; return ++next; }
int main(void) { @autoreleasepool {
    uint8_t control[2][0x880] = {{0}}, code[2][32] = {{1}, {2}};
    for (int i = 0; i < 2; i++) { uint32_t n = sizeof code[i]; memcpy(control[i] + 0x704, &n, 4); }
    prog_t source[2] = {{.magic = 1, .nstage = 1, .serial = 10}, {.magic = 1, .nstage = 1, .serial = 20}};
    for (int i = 0; i < 2; i++) source[i].sd[0] = (NVNshaderData){.data = (uintptr_t)code[i], .control = control[i]};
    program_stage_binding binding[6] = {{&source[0], 0}, {0}, {0}, {0}, {&source[1], 0}};
    const prog_t *first = program_binding_compose(binding);
    assert(first && first->nstage == 2);
    for (int i = 0; i < 10000; i++) {
        prog_t relocated[2] = {source[0], source[1]};
        relocated[0].serial = 100 + i * 2; relocated[1].serial = 101 + i * 2;
        binding[0].program = &relocated[0]; binding[4].program = &relocated[1];
        assert(program_binding_compose(binding) == first && "identical shaders must not retain a new composite for every source lifetime");
    }
    binding[0].program = &source[0]; binding[4].program = &source[1];
    source[1].serial++; code[1][1] = 3;
    const prog_t *changed = program_binding_compose(binding);
    assert(changed != first && "different shader code must not reuse a stale composite");
    binding[0] = (program_stage_binding){0}; binding[3] = (program_stage_binding){&source[0], 0};
    assert(program_binding_compose(binding) != changed && "stage assignment is part of program identity");
    puts("PASS: shader identity survives source retirement without merging different code/stages");
} }
