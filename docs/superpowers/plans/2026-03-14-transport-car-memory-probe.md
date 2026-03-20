# TransportCar Memory Probe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `TransportCar` 启动期加入原始 UART 内存打点, 便于板端定位初始化阶段的低内存崩溃位置。

**Architecture:** 在 `src/services/transport_car.py` 中新增一个不经过 logger 的最小内存打点 helper, 仅使用 `gc.collect()`、`gc.mem_free()`、`gc.mem_alloc()` 和 `uart3.write()` 输出关键初始化阶段的内存快照。先通过单测锁定输出格式与触发顺序, 再保留现有启动逻辑不变。

**Tech Stack:** Python, pytest, MicroPython gc API, UART text output

---

### Task 1: 为内存打点写失败测试

**Files:**
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

新增单测, 构造 `TransportCar` 最小依赖, monkeypatch `gc.collect`、`gc.mem_free`、`gc.mem_alloc`, 断言 `uart3` 收到以下打点标签:
- `boot.uart_ready`
- `boot.after_imu`
- `boot.after_drive`
- `boot.after_ident`
- `boot.before_gyro_offsets`
- `boot.after_gyro_offsets`

并断言输出走原始 `uart3.write`, 不依赖现有 logger 过滤。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: FAIL, 因为当前尚无这些内存打点输出

### Task 2: 加入最小内存打点实现

**Files:**
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write minimal implementation**

在 `TransportCar` 初始化链中加入一个 helper, 仅做:

```python
gc.collect()
free = gc.mem_free()
alloc = gc.mem_alloc()
self.uart3.write("MEM %s free=%s alloc=%s\r\n" % (label, free, alloc))
```

若宿主环境缺少 `mem_free/mem_alloc`, 则安全回退为 `na`。

**Step 2: Call helper at key checkpoints**

在关键节点依次调用:
- UART 初始化后
- IMU 初始化后
- 电机/编码器初始化后
- ident 参数加载后
- gyro offsets 前后

**Step 3: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS

### Task 3: 回归验证

**Files:**
- Test: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_remote_control_script.py`

**Step 1: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_remote_control_script.py -q`
Expected: 全绿

**Step 2: Hand off for board verification**

让用户将当前代码上传到板端, 重新跑 `boot.py` / `remote_control.py`, 观察 `MEM ...` 输出序列与最终崩点位置。
