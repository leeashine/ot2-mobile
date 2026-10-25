// Source: ot2-ios-route-a/host/gthread.h; commit daff9d0d3be6a8c388c137dbc52a3baf2ce029dd; project-owned, MIT.

// ot2-ios · 客体线程与内核同步原语（宿主侧）。
// 所有 svc 在一把全局递归锁下执行（ot2_svc_dispatch 入口加锁）；会阻塞的原语用同一把锁上的条件变量等待，等待时锁被释放。
#pragma once

#include <stdint.h>
typedef struct {
    uint32_t handle;
    uint64_t thread_id, guest_arg, tlr, host_pthread;
    int started, context_live;
} ot2_gthread_snapshot_row;


// ---- 全局锁（递归）与唤醒 ----
void ot2_big_lock(void);
void ot2_big_unlock(void);
void ot2_sync_wake_all(void);                   // 事件被信号等情况下唤醒所有等待者重新检查
int ot2_sync_d2r_enabled(void);
// OT2_SCHED=token：单协作令牌；core-token：每客体核一个令牌；
// preempt-token：单令牌并用 1–5 ms 信号时间片交接（诊断，种子由
// OT2_SCHED_PREEMPT_SEED 控制）。三种模式默认均关闭。
void ot2_guest_token_enter(void);
void ot2_guest_token_leave(void);
unsigned ot2_guest_token_suspend(void);
void ot2_guest_token_resume(unsigned depth);
// 显式诊断开关下，时间查询门周期性把协作 token 交给已排队客体线程。
void ot2_guest_token_time_query(void);
void ot2_guest_token_dump(void);
void ot2_guest_token_snapshot(int *enabled, int *active, uint32_t *owner_handle,
                              uint64_t *owner_pthread, uint64_t *owner_since_ns,
                              unsigned *waiters);
unsigned ot2_guest_token_waiting_snapshot(uint32_t *handles, unsigned capacity);


// ---- 互斥量仲裁（宿主 HLE 模型；Switchbrew SVC 页只列参数 ABI）----
// waiter 位与 word/tag 映射是当前实现假设，不是 Switchbrew 页面记录的语义。
#define OT2_MUTEX_HAS_WAITERS 0x40000000u
void ot2_sync_arbitrate_lock(uint32_t thread_handle, uint64_t addr, uint32_t tag);
void ot2_sync_arbitrate_unlock(uint64_t addr);

// ---- 进程宽条件变量 ----
// 返回 0 成功（返回时互斥量已重新持有）、0xEA01 超时（返回时互斥量未持有）。timeout_ns < 0 = 无限。
uint32_t ot2_sync_wait_process_wide_key(uint64_t mutex_addr, uint64_t key, uint32_t tag, int64_t timeout_ns);
int ot2_sync_signal_process_wide_key(uint64_t key, int32_t count);   // count <= 0 = 全部；返回被唤醒数

void ot2_sync_dump_last_cv(void);                // 诊断：打印最后一次条件变量等待的互斥量附近内存

// ---- 等待内核对象（目前是 kevent）----
// 默认实现保留“未登记句柄已信号”的兼容行为；d2r 备选实现返回
// 0xE401，并支持 CancelSynchronization 的一次性 0xEC01。
uint32_t ot2_sync_wait_handles(const uint32_t *handles, int n, int64_t timeout_ns, int *index);

// ---- 客体线程 ----
void ot2_gthread_create(uint32_t handle, uint64_t entry, uint64_t arg,
                        uint64_t stack_top, uint64_t thread_id,
                        int32_t priority, int32_t ideal_core);
int ot2_gthread_get_id(uint32_t handle, uint64_t *thread_id); // 0 成功；未登记返回 -1
int ot2_gthread_get_priority(uint32_t handle, int32_t *priority);
int ot2_gthread_set_priority(uint32_t handle, int32_t priority);
int ot2_gthread_get_core_mask(uint32_t handle, int32_t *ideal_core,
                              uint64_t *core_mask);
int ot2_gthread_set_core_mask(uint32_t handle, int32_t ideal_core,
                              uint64_t core_mask);
uint32_t ot2_gthread_current_processor(void);
int ot2_gthread_cancel(uint32_t handle);
int ot2_gthread_take_current_cancel(void);
int ot2_gthread_start(uint32_t handle);          // 0 成功；找不到记录返回 -1
void ot2_gthread_exit(void) __attribute__((noreturn));   // 在 svc 里调用：放锁并结束当前 pthread
unsigned ot2_gthread_count(void);
// Snapshot helpers; caller holds ot2_big_lock().
unsigned ot2_gthread_snapshot(ot2_gthread_snapshot_row *rows, unsigned capacity);
// 客体代码/宿主门边界；MM-STW 只暂停正在执行客体代码的 pthread。
void ot2_gthread_guest_begin(void);
int ot2_gthread_host_enter(void);
void ot2_gthread_guest_resume(int was_guest);
// OT2_MM_STW 诊断：调用者持有 g_big；暂停/恢复当前线程外的客体宿主线程。
int ot2_gthread_mm_stw_begin(void);
void ot2_gthread_mm_stw_end(void);
void ot2_sync_snapshot_waiters(uint64_t key, unsigned *cv_waiters,
                               unsigned *mutex_waiters);
uint32_t ot2_gthread_current_handle(void);        // 当前宿主线程对应的客体线程句柄
