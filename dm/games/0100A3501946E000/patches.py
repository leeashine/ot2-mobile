# OCTOPATH TRAVELER II 1.1.1: allocator replacement and opt-in widescreen gates.
# GCreateMalloc at main+0xbd4330 allocates 0x1c38 bytes, keeps the object in x19,
# and calls FMallocBinned3 at main+0xc34eb8. Its vtable at main+0x642c048 has
# 20 entries (Malloc/Free at slots 3/7); hle_uemalloc.c installs the host table.
# Only instruction encodings needed to assert the patch site are included here;
# rewritten images and all game assets remain local user inputs.
CUTS = {
    '65619a04b8a04b10d44f9996ef141062': [
        (0xbd4348, 'dc820194', '1f2003d5',
         'GCreateMalloc: skip FMallocBinned3 constructor; install host malloc-zone vtable at the following gate'),
    ],
}
OBS = {
    '65619a04b8a04b10d44f9996ef141062': [
        (0xbd434c, 21, 'aa1303e0',
         'OBS_UE_MALLOC: x19 holds the new allocator; original instruction mov x0, x19'),
        # UCameraComponent::GetCameraView: FOV at x19+0x18, aspect at +0x2c,
        # projection mode at +0x31. All were written before this instruction.
        # SetAspectRatio's reflected thunk (0x2f1759c) confirms component+0x204;
        # GetCameraView copies it at 0x277d508, after the FOV at 0x277d504.
        # The shared epilogue keeps x19 live and has no live caller-saved scratch
        # registers; patch_nso.py verifies this before inserting the gate.
        (0x277d644, 22, '6d5323e9',
         'OBS_UE_CAMERA: optional Hor+ projection; original ldp d9, d8, [sp, #0x130]'),
        # GetAnchorsInViewport's reflected thunk at 0x23bdb04 calls this
        # getter, which returns the four floats at UUserWidget+0x210..0x21c.
        (0x23144ac, 23, 'bd421000',
         'OBS_UE_VIEWPORT_ANCHORS: optional centered HUD; original ldr s0, [x0, #0x210]'),
    ],
}
