// Source: d2r-mobile/dm/host/dm.h; commit 9393b00ea9aca52d9254214da93738f26582562; MIT.
#pragma once

#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define LOG(...) do { fprintf(stderr, "[ot2-nvn] " __VA_ARGS__); fputc('\n', stderr); } while (0)
#define die(...) do { LOG("FATAL " __VA_ARGS__); abort(); } while (0)

uint64_t now_ns(void);
uint64_t guest_ns(void);
int dm_detclock_enabled(void);
void dm_guest_frame_tick(void);
int dm_guest_heap_stat(unsigned long long *total, unsigned long long *free_bytes,
                       unsigned long long *largest_block);
void dm_fault_hook_register(int (*fn)(void *address, int is_write, void *context));
void dm_guest_write_prep_register(void (*fn)(void *address, size_t length));
void dm_guest_write_prepare(void *address, size_t length);
void dm_res_report_register(void (*fn)(uint32_t tick, const char *reason));
void (*dm_res_report_cb(void))(uint32_t tick, const char *reason);
void dm_gfx_suspend(int on);
void dm_shot_written(const char *path, int ok);
void dm_host_shutdown(const char *why);
uint32_t dm_guest_work_qos(unsigned *count);
void dm_main_yield_stats(uint64_t *count, uint64_t *nanoseconds);
double dm_brightness_now(void);
void dm_perf_present(double interval_ms);
int dm_thermal_now(void);
void dm_longframe_note(const char *what);
int dm_diag_player_fixed(uint32_t *x, uint32_t *y);
uint64_t dm_focus_in_since(void);
uint64_t dm_prof_ribbon_ns(void);
