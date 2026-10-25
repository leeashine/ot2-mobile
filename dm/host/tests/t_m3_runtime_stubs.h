// Test-only process globals; no guest modules or entry thunks are executed.
struct dm_flags g_flag;
module_t g_mod[MAX_MOD]; int g_nmod;
uint64_t g_t0_ns;
uint64_t (*g_ub_sub_cpu_ns)(void), (*g_ub_sub_cyc)(void);
void *nvn_thunk[523]; const char *nvn_names[523];
void nvn_framechk_entry(void) { abort(); }
void nvn_unimpl_entry(void) { abort(); }
void nvn_prof_entry(void) { abort(); }
