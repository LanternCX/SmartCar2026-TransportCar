# Remove TransportCar Memory Probe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在保留 `gyro offset` 启动日志修复的前提下, 移除临时 `TransportCar` 内存打点代码与对应测试。

**Architecture:** 先通过测试锁定启动路径不再输出 `MEM ...` 调试文本, 再删除 `TransportCar` 中的内存打点 helper 与调用点。保留“`load_gyro_offsets()` 不接 `INFO` logger”这一行为修复不变, 最后回归相关单测。

**Tech Stack:** Python, pytest

---

### Task 1: 为移除打点写失败测试

**Files:**
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

新增或调整单测, 断言 `TransportCar(vehicle_role="main")` 启动后, `uart3.messages` 中不再出现以 `MEM ` 开头的调试行。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: FAIL, 因为当前仍会输出 `MEM ...` 行

### Task 2: 删除临时内存打点

**Files:**
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write minimal implementation**

删除:
- `_emit_memory_probe()` helper
- `boot.uart_ready`
- `boot.after_imu`
- `boot.after_drive`
- `boot.after_ident`
- `boot.before_gyro_offsets`
- `boot.after_gyro_offsets`

保留:
- `load_gyro_offsets(GYRO_OFFSET_FILE)` 不再传入 logger

**Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS

### Task 3: 回归验证

**Files:**
- Test: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_remote_control_script.py`

**Step 1: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_remote_control_script.py -q`
Expected: 全绿
