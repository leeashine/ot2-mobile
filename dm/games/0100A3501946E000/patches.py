# OCTOPATH TRAVELER II 1.1.1: build-specific UE allocator replacement.
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
    ],
}
