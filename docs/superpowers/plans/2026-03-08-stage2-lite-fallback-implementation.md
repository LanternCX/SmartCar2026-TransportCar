# Stage2 Full/Lite Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在低内存板端上为 `stage2` 提供 `full -> lite` 自动回退，让最小可信探针可通过，同时尽量不污染业务代码。

**Architecture:** 保持 `TransportCar` 业务路径不新增测试专用接口，优先在 `src/services/stage2_smoke.py` 中封装 `full` 与 `lite` 两种收集流程。主机侧执行器 `tools/run_stage2_smoke.py` 只负责接受两种模式并按模式校验成功条件。

**Tech Stack:** Python, pytest, MicroPython runtime constraints, mpy-cli

---

### Task 1: 锁定当前失败测试

**Files:**
- Test: `tests/unit/services/test_transport_car_diag_mode.py`
- Test: `tests/unit/tools/test_run_stage2_smoke.py`

**Step 1: 运行 `stage2` 回退相关测试**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py::test_stage2_smoke_probe_falls_back_to_lite_mode_on_transport_memory_error tests/unit/tools/test_run_stage2_smoke.py::test_parse_probe_output_accepts_lite_mode_when_query_chain_is_ok -q`

**Step 2: 确认失败原因**

Expected: `collect_stage2_summary()` 未回退到 `lite`，以及主机侧解析仍拒绝 `mode=lite`。

### Task 2: 实现运行时 full/lite 双路径

**Files:**
- Modify: `src/services/stage2_smoke.py`
- Test: `tests/unit/services/test_transport_car_diag_mode.py`

**Step 1: 保持既有 full 收集逻辑独立**

把完整 `TransportCar(diagnostic_mode=True)` 路径下沉为 `_collect_full_transport_summary()`，避免与回退逻辑耦合。

**Step 2: 增加 lite 收集逻辑**

实现 `_collect_lite_transport_summary()`，只验证轻量导入、query 可达性、关键源码入口存在性，并返回 `mode=lite init=0 queries=1 step=0 tick_count=0 snapshots=none`。

**Step 3: 增加回退选择**

在 `collect_stage2_summary()` 中先尝试 full；若出现 `MemoryError` 或可识别的受限导入异常，则退到 lite。

### Task 3: 更新主机侧解析规则

**Files:**
- Modify: `tools/run_stage2_smoke.py`
- Test: `tests/unit/tools/test_run_stage2_smoke.py`

**Step 1: 按模式区分校验条件**

`mode=full` 继续要求 `init=1 step=1 snapshots` 完整；`mode=lite` 只要求 `queries=1`，允许 `init=0 step=0 snapshots=none`。

**Step 2: 保持失败归因清晰**

保留 `probe_failed` 与具体 reason，避免把 lite 当成无条件成功。

### Task 4: 主机回归验证

**Files:**
- Test: `tests/unit/services/test_transport_car_diag_mode.py`
- Test: `tests/unit/tools/test_run_stage2_smoke.py`
- Test: `tests/unit`
- Test: `tests/contract`

**Step 1: 跑目标单测**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py tests/unit/tools/test_run_stage2_smoke.py -q`

**Step 2: 跑主机全集**

Run: `python3 -m pytest tests/unit tests/contract -q`

### Task 5: 真板验证

**Files:**
- Modify: none
- Run: `tools/run_stage2_smoke.py`

**Step 1: 在真实端口执行 stage2**

Run: `python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem11101`

**Step 2: 记录实际模式**

Expected: 至少得到 `status=ok`，模式可为 `full` 或 `lite`。

**Step 3: 如稳定通过，再清理临时诊断脚本**

仅在正式链路稳定后删除 `tools/tmp_*probe.py`。
