# Vision Log Noise And Formatter Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 降低运行期视觉轮询日志噪声并减少日志格式化的瞬时分配, 以缓解板端 OOM 风险。

**Architecture:** 保持日志系统结构不变, 仅把高频 `POLL camera=...` 从 `INFO` 下调到 `DEBUG`, 让默认 `RUN` 档不再每拍刷屏, 同时保留 `FRAME camera=...` 为 `INFO` 方便设备观测。随后在 `diagnostics.format` 中把 `sanitize_log_text()` 改为更低分配的实现, 在不改变输出语义的前提下降低碎片化风险。

**Tech Stack:** Python, pytest, MicroPython-friendly string formatting

---

### Task 1: 锁定默认运行档不输出高频 POLL 日志

**Files:**
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

调整现有视觉日志测试, 让其断言默认 `LogManager()` 配置下:
- 不出现 `POLL camera=...`
- 仍出现 `FRAME camera=... end detections=...`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py::test_transport_car_vision_frame_boundary_logs_without_poll_noise -q`
Expected: FAIL, 因为当前 `POLL` 仍然是 `INFO`

### Task 2: 最小修正视觉日志等级

**Files:**
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write minimal implementation**

把 `_log_vision_poll()` 从 `self.log_vision.info(...)` 改为 `self.log_vision.debug(...)`, 保留 `_log_vision_frame_boundary()` 为 `INFO`。

**Step 2: Run focused test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py::test_transport_car_vision_frame_boundary_logs_without_poll_noise -q`
Expected: PASS

### Task 3: 低分配重构日志格式化

**Files:**
- Modify: `src/diagnostics/format.py`
- Test: `tests/unit/services/test_logging.py`

**Step 1: Refactor safely**

将 `sanitize_log_text()` 改为更低分配实现, 目标是在常见 ASCII 输入上减少中间对象创建, 同时保持现有输出语义不变。

**Step 2: Run formatter tests**

Run: `python3 -m pytest tests/unit/services/test_logging.py -q`
Expected: PASS

### Task 4: 回归验证

**Files:**
- Test: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_logging.py`
- Test: `tests/unit/services/test_remote_control_script.py`

**Step 1: Run focused regression**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_logging.py tests/unit/services/test_remote_control_script.py -q`
Expected: 全绿
