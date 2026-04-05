# 主辅运行时控制边界与迁移补完实施计划

> **给执行代理的要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划，步骤使用复选框 `- [ ]` 跟踪。

**目标：** 把主辅主线改成以过程式链路为主的实现，统一收口跨控制周期状态，补齐 `stability` 迁移闭环，并让控制职责真正回到 `ctrl/`。

**架构：** 先删除会奖励兼容层、目录形状和旧入口壳的测试噪音，只保留真实行为基线；再盘点并冻结当前主链行为，然后把主线改写成清楚的过程式链路，把跨控制周期变量统一迁入 `state/`，再按“滤波/姿态 -> 运动学/控制器”的顺序把控制实现从 `motion_runtime.py` 迁回 `ctrl/`。文档产物和测试都与每一轮迁移同步生成，不留“最后再补”的尾巴。

**技术栈：** Python 3.8+、MicroPython 兼容代码、pytest、主辅双包运行时、过程式主循环、板端 HIL 文档。

---

## 文件结构与职责

- Create: `docs/superpowers/reference/2026-04-02-motion-runtime-split-checklist.md`
  记录主辅 `motion_runtime.py` 现有内容按“状态 / 控制 / 硬件 / 调度 / 序列化”的拆分清单。
- Create: `docs/superpowers/reference/2026-04-02-state-control-placement-map.md`
  记录长期状态、控制内部状态和 owner 装配状态的统一落位对照。
- Create: `docs/superpowers/reference/2026-04-02-stability-migration-table.md`
  记录旧 `stability` 能力的原位置、现位置、去留结论、依据与验证方式。
- Create: `src/master/state/__init__.py`
  提供主车跨控制周期状态统一入口。
- Modify: `src/assistant/state/__init__.py`
  扩展为辅车跨控制周期状态统一入口。
- Modify: `src/master/ctrl/filters.py`
  承接主车滤波链真实实现。
- Modify: `src/assistant/ctrl/filters.py`
  承接辅车滤波链真实实现。
- Modify: `src/master/ctrl/attitude.py`
  承接主车姿态估计与旧姿态辅助能力。
- Modify: `src/assistant/ctrl/attitude.py`
  承接辅车姿态估计与旧姿态辅助能力。
- Modify: `src/master/ctrl/kinematics.py`
  承接主车运动学、位移换算和里程更新辅助。
- Modify: `src/assistant/ctrl/kinematics.py`
  承接辅车运动学、位移换算和里程更新辅助。
- Modify: `src/master/ctrl/pid.py`
  承接主车轮速控制器入口。
- Modify: `src/assistant/ctrl/pid.py`
  承接辅车轮速控制器入口。
- Modify: `src/master/motion_runtime.py`
  改写为主车过程式主线入口，只保留调度、硬件编排和状态装配。
- Modify: `src/assistant/motion_runtime.py`
  改写为辅车过程式主线入口，只保留调度、硬件编排和状态装配。
- Modify: `src/master/app.py`
  接入主车新的过程式主线入口。
- Modify: `src/assistant/app.py`
  接入辅车新的过程式主线入口。
- Modify: `src/assistant/status.py`
  只保留最小状态序列化入口。
- Delete: `src/assistant/ctrl/chassis.py`
  删除空壳边界。
- Modify: `tests/unit/master/test_structure_runtime.py`
  保护主车过程式主线与状态边界。
- Modify: `tests/unit/assistant/test_structure_runtime.py`
  保护辅车过程式主线与状态边界。
- Modify: `tests/unit/master/test_app.py`
  保护主车过程式入口装配。
- Modify: `tests/unit/assistant/test_app.py`
  保护辅车过程式入口装配。
- Modify: `tests/unit/master/test_stability_baseline.py`
  保护主车稳定与滤波主链承接结果。
- Modify: `tests/unit/assistant/test_stability_baseline.py`
  保护辅车稳定与滤波主链承接结果。
- Modify: `tests/unit/assistant/test_status.py`
  保护辅车状态对象与最小状态回包边界。
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
  保护辅车最小状态回传契约不变。
- Modify if needed: `tests/hil/2026-04-01-master-minimal-runtime.md`
  若主车入口或观测点变化，则同步更新。
- Modify if needed: `tests/hil/2026-04-01-assistant-minimal-runtime.md`
  若辅车入口或观测点变化，则同步更新。

### Task 1: 先删除会奖励兼容层的测试

**Files:**
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`

- [ ] **步骤 1：盘点当前测试中哪些断言只是在保护旧入口、旧壳层、目录形状或符号存在**

- [ ] **步骤 2：先删除主车中会奖励兼容层的测试断言，只保留真实行为基线**

- [ ] **步骤 3：先删除辅车中会奖励兼容层的测试断言，只保留真实行为基线**

- [ ] **步骤 4：运行相关测试，确认删掉的是结构噪音而不是主线行为保护**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py -q`
Expected: PASS，剩下的失败若存在，应只指向真实行为问题，而不是旧兼容层缺失。

### Task 2: 盘点现状并冻结三份基线产物

**Files:**
- Create: `docs/superpowers/reference/2026-04-02-motion-runtime-split-checklist.md`
- Create: `docs/superpowers/reference/2026-04-02-state-control-placement-map.md`
- Create: `docs/superpowers/reference/2026-04-02-stability-migration-table.md`
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`

- [ ] **步骤 1：逐段盘点主辅 `motion_runtime.py` 现有内容并写入拆分清单**

```markdown
| 文件 | 现有段落/对象 | 当前职责 | 目标落点 | 是否暂留 owner | 暂留理由 |
| --- | --- | --- | --- | --- | --- |
| src/master/motion_runtime.py | _LowPassFilter | 控制滤波 | src/master/ctrl/filters.py | 否 | - |
| src/assistant/motion_runtime.py | hw_bundle | 装配状态 | owner | 是 | 硬件句柄属于调度装配态 |
```

- [ ] **步骤 2：按“业务状态 / 控制内部状态 / owner 装配状态”写出落位对照初稿**

```markdown
| 变量或状态 | 当前所在处 | 目标落点 | 说明 |
| --- | --- | --- | --- |
| heading_deg | motion_runtime.py | state | 跨周期业务状态 |
| yaw_integral | motion_runtime.py | state | 跨周期控制内部状态 |
| hw_bundle | motion_runtime.py | owner | 装配态 |
```

- [ ] **步骤 3：按旧 `stability` 文件逐项建立迁移对表初稿**

```markdown
| 原文件 | 原能力 | 当前现状 | 目标动作 |
| --- | --- | --- | --- |
| src/master/stability/filtering.py | build_speed_filter_chain | 主链仍在 runtime 私有实现中 | 迁入 ctrl/filters |
```

- [ ] **步骤 4：为“主线仍可驱动、状态仍可更新、滤波链仍可工作”写失败测试，不再只测符号存在**

```python
def test_master_runtime_cycle_updates_heading_and_odom_snapshot() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)
    snapshot = runtime.run_base_cycle(state, hw_bundle=None)

    assert "heading_est_deg" in snapshot
    assert "odom" in snapshot
```

- [ ] **步骤 5：运行基线测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py -q`
Expected: FAIL，失败点指向过程式主线入口、状态落位或稳定链承接入口尚未建立。

- [ ] **步骤 6：在拆分清单中补全“最终暂留 owner 的内容与理由”栏位，作为后续迁移复核基线**

### Task 3: 先把主车主线改成过程式链路

**Files:**
- Modify: `src/master/motion_runtime.py`
- Modify: `src/master/app.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_structure_runtime.py`

- [ ] **步骤 1：为主车过程式入口写失败测试**

```python
def test_master_runtime_process_entry_drives_one_cycle() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)
    result = runtime.run_base_cycle(state, hw_bundle=None)

    assert isinstance(result, dict)
```

- [ ] **步骤 2：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/master/test_structure_runtime.py -q`
Expected: FAIL，失败点指向主车仍依赖大对象方法而非过程式入口。

- [ ] **步骤 3：建立主车 `create_runtime_state()` 过程式状态装配入口**

```python
def create_runtime_state(hw_bundle=None):
    ...
```

- [ ] **步骤 4：建立主车 `run_base_cycle()` 过程式单拍入口**

```python
def run_base_cycle(state, hw_bundle=None, cycle_token=None):
    ...
```

- [ ] **步骤 5：让 `src/master/app.py` 调用新的过程式入口**

- [ ] **步骤 6：运行主车入口测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/master/test_structure_runtime.py -q`
Expected: PASS。

### Task 4: 再把辅车主线改成过程式链路并删掉空壳

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/app.py`
- Delete: `src/assistant/ctrl/chassis.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **步骤 1：为辅车过程式入口写失败测试**

```python
def test_assistant_runtime_process_entry_drives_one_cycle() -> None:
    import assistant.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)
    result = runtime.run_base_cycle(state, hw_bundle=None, now_ms=0)

    assert isinstance(result, str)
```

- [ ] **步骤 2：为“空壳模块已移除且主线不再依赖它”写失败测试**

```python
def test_assistant_ctrl_chassis_module_is_removed() -> None:
    import importlib.util

    assert importlib.util.find_spec("assistant.ctrl.chassis") is None
```
```
def test_assistant_runtime_process_entry_runs_without_ctrl_chassis_shell() -> None:
    import assistant.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)
    result = runtime.run_base_cycle(state, hw_bundle=None, now_ms=0)

    assert isinstance(result, str)
```

- [ ] **步骤 3：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: FAIL，失败点指向辅车仍依赖大对象方法或空壳仍存在。

- [ ] **步骤 4：建立辅车 `create_runtime_state()` 过程式状态装配入口**

- [ ] **步骤 5：建立辅车 `run_base_cycle()` 与 `apply_runtime_command()` 过程式入口**

- [ ] **步骤 6：删除 `src/assistant/ctrl/chassis.py` 并清理相关导入**

- [ ] **步骤 7：运行辅车入口测试确认通过**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。

### Task 5: 统一把跨控制周期变量迁入 `state/`

**Files:**
- Create: `src/master/state/__init__.py`
- Modify: `src/assistant/state/__init__.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `docs/superpowers/reference/2026-04-02-state-control-placement-map.md`
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_status.py`

- [ ] **步骤 1：为主车 `state/` 统一入口写失败测试**

```python
def test_master_state_module_owns_cross_cycle_state() -> None:
    from master.state import MasterRuntimeState, MasterControlState

    runtime_state = MasterRuntimeState()
    control_state = MasterControlState()

    assert hasattr(runtime_state, "heading_deg")
    assert hasattr(control_state, "yaw_integral")
```

- [ ] **步骤 2：为辅车控制内部状态统一进 `state/` 写失败测试**

```python
def test_assistant_control_state_is_kept_under_state_module() -> None:
    from assistant.state import AssistantState, AssistantControlState

    state = AssistantState()
    control_state = AssistantControlState()

    assert hasattr(state, "follow_active")
    assert hasattr(control_state, "follow_target_world")
```

- [ ] **步骤 3：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_status.py -q`
Expected: FAIL，失败点指向跨周期变量仍散落在 `motion_runtime.py`。

- [ ] **步骤 4：创建主车状态入口并按盘点结果迁入长期状态与控制内部状态**

- [ ] **步骤 5：扩展辅车状态入口并按盘点结果迁入长期状态与控制内部状态**

- [ ] **步骤 6：更新落位对照文档，逐项记录哪些变量进入 `state/`、哪些保留在 owner**

- [ ] **步骤 7：运行状态边界测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_status.py -q`
Expected: PASS。

### Task 6: 先迁滤波与姿态能力回 `ctrl/`

**Files:**
- Modify: `src/master/ctrl/filters.py`
- Modify: `src/assistant/ctrl/filters.py`
- Modify: `src/master/ctrl/attitude.py`
- Modify: `src/assistant/ctrl/attitude.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`

- [ ] **步骤 1：为主车滤波真实入口写失败测试**

```python
def test_master_filter_chain_filters_speed_samples() -> None:
    from master.ctrl.filters import build_speed_filter_chain

    chain = build_speed_filter_chain()
    filtered = chain.update(10.0)

    assert isinstance(filtered, float)
```

- [ ] **步骤 2：为辅车姿态估计真实入口写失败测试**

```python
def test_assistant_heading_estimator_updates_yaw() -> None:
    from assistant.ctrl.attitude import HeadingEstimator

    estimator = HeadingEstimator()
    estimator.update(0.0, 0.0, 0.0, 0.01)

    assert isinstance(estimator.yaw_rad(), float)
```

- [ ] **步骤 3：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py -q`
Expected: FAIL，失败点指向滤波链和姿态估计仍在 runtime 私有实现中。

- [ ] **步骤 4：迁出主车滤波链到 `src/master/ctrl/filters.py`**

- [ ] **步骤 5：让主车主线改接入新的滤波入口**

- [ ] **步骤 6：迁出辅车滤波链到 `src/assistant/ctrl/filters.py`**

- [ ] **步骤 7：让辅车主线改接入新的滤波入口**

- [ ] **步骤 8：迁出主车姿态估计能力到 `src/master/ctrl/attitude.py`**

- [ ] **步骤 9：让主车主线改接入新的姿态入口**

- [ ] **步骤 10：迁出辅车姿态估计能力到 `src/assistant/ctrl/attitude.py`**

- [ ] **步骤 11：让辅车主线改接入新的姿态入口**

- [ ] **步骤 12：运行滤波与姿态测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py -q`
Expected: PASS。

### Task 7: 再迁运动学与控制器能力回 `ctrl/`

**Files:**
- Modify: `src/master/ctrl/kinematics.py`
- Modify: `src/assistant/ctrl/kinematics.py`
- Modify: `src/master/ctrl/pid.py`
- Modify: `src/assistant/ctrl/pid.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **步骤 1：为位移换算和运动学入口写失败测试**

```python
def test_assistant_kinematics_rotates_body_delta_into_world() -> None:
    from assistant.ctrl.kinematics import rotate_body_delta_to_world

    world_x, world_y = rotate_body_delta_to_world(10.0, 0.0, 90.0)

    assert isinstance(world_x, float)
    assert isinstance(world_y, float)
```

- [ ] **步骤 2：为轮速控制器入口写失败测试**

```python
def test_master_pid_controller_updates_output_from_state() -> None:
    from master.ctrl.pid import SpeedControllerState, update_speed_controller

    state = SpeedControllerState()
    output = update_speed_controller(state, target=1.0, now=0.0, dt_s=0.01)

    assert isinstance(output, float)
```

- [ ] **步骤 3：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: FAIL，失败点指向运动学或控制器仍留在 runtime 私有实现中。

- [ ] **步骤 4：迁出主车运动学与里程更新辅助到 `src/master/ctrl/kinematics.py`**

- [ ] **步骤 5：让主车主线改接入新的运动学入口**

- [ ] **步骤 6：迁出辅车运动学与里程更新辅助到 `src/assistant/ctrl/kinematics.py`**

- [ ] **步骤 7：让辅车主线改接入新的运动学入口**

- [ ] **步骤 8：迁出主车轮速控制器入口到 `src/master/ctrl/pid.py`，控制器跨周期状态继续由 `state/` 持有**

- [ ] **步骤 9：让主车主线改接入新的控制器入口**

- [ ] **步骤 10：迁出辅车轮速控制器入口到 `src/assistant/ctrl/pid.py`，控制器跨周期状态继续由 `state/` 持有**

- [ ] **步骤 11：让辅车主线改接入新的控制器入口**

- [ ] **步骤 12：运行运动学与控制器测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。

### Task 8: 逐项完成 `stability` 对表并处理缺失或退役结论

**Files:**
- Modify: `docs/superpowers/reference/2026-04-02-stability-migration-table.md`
- Modify: `src/master/ctrl/filters.py`
- Modify: `src/assistant/ctrl/filters.py`
- Modify: `src/master/ctrl/attitude.py`
- Modify: `src/assistant/ctrl/attitude.py`
- Modify: `src/master/ctrl/kinematics.py`
- Modify: `src/assistant/ctrl/kinematics.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`

- [ ] **步骤 1：把旧 `stability` 中每个能力逐项写入迁移表，不接受只按大类概述**

- [ ] **步骤 2：为每项能力补上现状标签，至少标明“当前在主线运行 / 当前仍在 runtime 私有实现 / 已迁入 ctrl / 已退役”**

- [ ] **步骤 3：单独处理 `euler_to_quaternion` 与 `quaternion_to_euler` 的去留结论**

- [ ] **步骤 4：单独处理 `body_axis_semantics` 与 `HeadingController` 的去留结论**

- [ ] **步骤 5：单独处理 `build_speed_filter_chain` 与 `build_gyro_filter` 的去留结论**

- [ ] **步骤 6：若某项能力对车自身状态稳定或滤波链路通畅仍必要，则补回真实落点并补测试**

- [ ] **步骤 7：若某项能力正式退役，则在迁移表里写明删除依据与替代关系**

- [ ] **步骤 8：运行稳定链测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py -q`
Expected: PASS。

### Task 9: 补齐注释、状态回包边界与总回归

**Files:**
- Modify: `src/master/motion_runtime.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/master/state/__init__.py`
- Modify: `src/assistant/state/__init__.py`
- Modify: `src/master/ctrl/filters.py`
- Modify: `src/assistant/ctrl/filters.py`
- Modify: `src/master/ctrl/attitude.py`
- Modify: `src/assistant/ctrl/attitude.py`
- Modify: `src/master/ctrl/kinematics.py`
- Modify: `src/assistant/ctrl/kinematics.py`
- Modify: `src/master/ctrl/pid.py`
- Modify: `src/assistant/ctrl/pid.py`
- Modify: `src/assistant/status.py`
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
- Modify if needed: `tests/hil/2026-04-01-master-minimal-runtime.md`
- Modify if needed: `tests/hil/2026-04-01-assistant-minimal-runtime.md`

- [ ] **步骤 1：补齐 `motion_runtime.py`、`state/` 和迁移承接文件的职责边界注释**

- [ ] **步骤 2：确认 `src/assistant/status.py` 只消费状态对象并维持最小状态回包契约**

- [ ] **步骤 3：运行辅车状态合同测试确认通过**

Run: `python3 -m pytest tests/unit/assistant/test_status.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS。

- [ ] **步骤 4：若主线入口或观测点变化，则同步更新 HIL 文档**

- [ ] **步骤 5：运行主机侧总回归**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **步骤 6：人工复核最终产物是否齐全**

```text
1. motion_runtime 拆分清单
2. 状态与控制落位对照说明
3. stability 逐项迁移对表
4. 过程式主线入口
5. state 统一状态入口
6. ctrl 真实控制落点
7. 注释补齐
8. 相关测试通过
```
