// iOS does not expose <mach/mach_vm.h>; these NVN diagnostics only read the current task, so use the public same-task vm_read_overwrite API.
#pragma once
#include <mach/mach.h>
#include <mach/vm_map.h>
#define mach_vm_read_overwrite vm_read_overwrite
