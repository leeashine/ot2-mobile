// Source: d2r-mobile/dm/host/front.h; commit 9393b00ea9aca52d9254214da93738f26582562; MIT.
#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void *front_metal_layer(void);
double front_display_refresh(char *name, size_t size);
int ot2_front_run(void (*guest_entry)(void *), void *context);
void ot2_front_request_stop(void);

#ifdef __cplusplus
}
#endif
