# Vision Runtime Memory Footprint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不大改视觉架构的前提下, 减少主控视觉链路运行期对象与短生命周期分配, 降低板端 OOM 风险并保留可调试性。

**Architecture:** 保持 `TransportCar -> VisionCoordinator -> VisionProtocol -> VisionStateMachine` 现有分层不变, 只收敛高频路径上的对象开销。第一类改动是为高频小对象加 `__slots__`, 降低实例常驻开销; 第二类改动是缓存视觉调试 sink 与轮询顺序, 去掉每拍重复 closure / list 分配。

**Tech Stack:** Python, pytest, MicroPython-friendly runtime objects

---

### Task 1: 为视觉小对象锁定低占用约束

**Files:**
- Modify: `tests/unit/services/test_vision_protocol.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

补测试断言以下对象不暴露 `__dict__`, 以锁定 `__slots__` 优化:
- `vision.protocol.VisionFrame`
- `vision.protocol.VisionObservation`
- `vision.protocol.VisionParseResult`
- `vision.coordinator.VisionRefreshResult`
- `vision.debug.VisionTransitionEvent`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_transport_car_vision_integration.py -k slots -q`
Expected: FAIL, 因为当前这些对象仍带 `__dict__`

### Task 2: 锁定 TransportCar 视觉高频辅助对象不重复分配

**Files:**
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

补测试断言:
- `TransportCar._get_vision_camera_poll_order()` 连续调用返回同一个顺序对象
- `TransportCar._emit_vision_debug()` 使用缓存 sink, 不在每次调用时重新构造 logger closure

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -k "poll_order or cached_debug_sink" -q`
Expected: FAIL, 因为当前实现会反复 `list(...)` 且每次 `build_logger_debug_sink(...)`

### Task 3: 实现最小低内存优化

**Files:**
- Modify: `src/vision/protocol.py`
- Modify: `src/vision/coordinator.py`
- Modify: `src/vision/debug.py`
- Modify: `src/services/transport_car.py`

**Step 1: Write minimal implementation**

按测试最小化修改:
- 为 5 个高频对象补 `__slots__`
- 在 `TransportCar` 中缓存视觉调试 sink
- 让视觉轮询顺序复用常量序列, 不再每次复制 `list`

**Step 2: Run focused tests to verify they pass**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

### Task 4: 回归验证与记录

**Files:**
- Modify: `docs/superpowers/memory/refactor/entries/2026-03/2026-03-15-1.md`
- Modify: `docs/superpowers/memory/refactor/INDEX.md`
- Test: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_vision_state_machine.py`

**Step 1: Run regression**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py -q`
Expected: 全绿

**Step 2: Update memory**

将本轮结论追加到 `docs/superpowers/memory/`, 记录:
- 已保留的最小代码级内存优化
- 这类 OOM 既可能来自代码侧对象生命周期 / 泄漏问题, 也可能与板子硬件或 MicroPython 固件状态异常有关
