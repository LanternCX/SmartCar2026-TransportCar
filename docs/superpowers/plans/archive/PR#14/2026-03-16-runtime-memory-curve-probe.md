# 运行时内存曲线探针 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在搬运车真实启动与 lazy 路径上输出板端内存曲线, 用于对比 `master` 与 `dev` 的 import/init/首次访问峰值差异。

**Architecture:** 采用最小侵入的运行时埋点方案, 在 `TransportCar` 核心入口提供统一内存 trace 输出接口, 再在 `remote_control` 启动路径和 `CompatMixin` 的关键 lazy 路径插入阶段打点。输出统一走 `uart3`, 便于用户直接上传到板端并观察串口曲线。

**Tech Stack:** Python, MicroPython, pytest, uart3 trace

---

### Task 1: 为运行时内存曲线探针补测试并实现最小埋点

**Files:**
- Modify: `tests/unit/services/test_remote_control_script.py`
- Modify: `src/services/car/core.py`
- Modify: `src/services/car/compat.py`
- Modify: `src/script/remote_control.py`

- [ ] **Step 1: 写失败测试**

```python
def test_remote_control_emits_memory_trace_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    ...
    assert any("TRACE mem stage=after_core_init" in msg for msg in module.car.uart3.messages)
    assert any("TRACE mem stage=before_first_step" in msg for msg in module.car.uart3.messages)
```

并补一个 `CompatMixin` 相关单测, 断言首次 `_ensure_uart_ingress()` 或 lazy vision 访问时会调用统一 trace 接口。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_remote_control_script.py -q`
Expected: FAIL, 因当前尚未输出内存曲线阶段

- [ ] **Step 3: 写最小实现**

```python
def _trace_mem(self, stage: str) -> None:
    ...
    self.uart3.write("TRACE mem stage=%s free=%d\r\n" % (stage, free_bytes))
```

在以下阶段埋点:
- `remote_control.py`
  - `after_import_transport_car`
  - `before_core_init`
  - `after_core_init`
  - `before_first_step`
  - `after_first_step`
- `compat.py`
  - `before_lazy_vision_attr`
  - `after_lazy_vision_attr`
  - `before_uart_ingress_init`
  - `after_uart_ingress_init`

异常路径输出:

```python
self.uart3.write("TRACE fail stage=%s type=%s\r\n" % (stage, exc_type))
```

- [ ] **Step 4: 跑 focused tests**

Run: `python3 -m pytest tests/unit/services/test_remote_control_script.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_uart_ingress.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/services/test_remote_control_script.py src/services/car/core.py src/services/car/compat.py src/script/remote_control.py
git commit -m "test(services): add runtime memory curve traces"
```
