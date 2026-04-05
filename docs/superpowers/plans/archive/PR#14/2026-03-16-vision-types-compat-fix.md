# vision.py types 兼容修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 去掉 `services.car.vision` 对 `types.SimpleNamespace` 的板端依赖, 修复裸板 `ImportError: no module named 'types'`。

**Architecture:** 保持 `VisionMixin` 的懒装配结构不变, 仅把禁用视觉路径使用的轻量服务占位对象改为模块内本地最小容器。先补 MicroPython 兼容失败测试, 再做最小实现, 最后用 focused tests 验证视觉集成不回退。

**Tech Stack:** Python, MicroPython, pytest, repo-local `docs/superpowers/memory/`

---

### Task 1: 修复 `services.car.vision` 的 `types` 依赖

**Files:**
- Modify: `tests/unit/services/test_micropython_compatibility.py`
- Modify: `src/services/car/vision.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `docs/superpowers/memory/debug/INDEX.md`
- Create: `docs/superpowers/memory/debug/entries/2026-03/2026-03-16-1.md`

**Step 1: 写失败测试**

```python
def test_services_car_vision_module_loads_without_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_module_import(monkeypatch, "types")
    module = _load_module_from_path(
        "services.car.vision",
        _module_path("src/services/car/vision.py"),
    )
    assert hasattr(module, "VisionMixin")
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_micropython_compatibility.py -k vision_module_loads_without_types -q`
Expected: FAIL, 因当前模块顶层导入 `types`

**Step 3: 写最小实现**

```python
class _DisabledVisionService:
    def __init__(self, enabled, vision_runtime, vision_coordinator):
        self.enabled = enabled
        self.vision_runtime = vision_runtime
        self.vision_coordinator = vision_coordinator
```

并把禁用视觉路径的 `types.SimpleNamespace(...)` 替换为该本地对象, 同时移除顶层 `import types`

**Step 4: 跑 focused tests**

Run: `python3 -m pytest tests/unit/services/test_micropython_compatibility.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

**Step 5: 记录进度**

- 在 `docs/superpowers/memory/debug/entries/2026-03/2026-03-16-1.md` 记录当前板端错误链已从 OOM 后移到 `types` 缺失, 以及本轮兼容修复
- 在 `docs/superpowers/memory/debug/INDEX.md` 追加索引行

**Step 6: Commit**

```bash
git add tests/unit/services/test_micropython_compatibility.py src/services/car/vision.py docs/superpowers/memory/debug/INDEX.md docs/superpowers/memory/debug/entries/2026-03/2026-03-16-1.md
git commit -m "fix(vision): remove types dependency from lazy vision service"
```
