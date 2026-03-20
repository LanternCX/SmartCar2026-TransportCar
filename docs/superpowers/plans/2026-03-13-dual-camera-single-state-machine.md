# 主车双摄单状态机协同 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为主车双摄正交、主车唯一任务状态机、辅车纯执行和 `boot` 角色入口方案补齐协议、启动入口与运行时实现。

**Architecture:** 先用文档和测试锁定主车/辅车角色边界、双摄轮询约束与单次查询多条检测响应语义, 再分步实现 `boot` 角色选择、视觉协议升级、双摄轮询和主车/辅车 profile。主车统一消费双摄观测并维护唯一任务状态机, 辅车只保留执行链路和状态回传。

**Tech Stack:** Python, pytest unit/contract tests, MicroPython compatibility checks, Stage 2 smoke, Stage 3 uart observe, HIL evidence.

---

### Task 1: 锁定 `boot` 角色与按钮启动语义

**Files:**
- Create: `tests/unit/services/test_boot_script.py`
- Modify: `src/boot.py`
- Modify: `src/script/remote_control.py`
- Modify: `docs/Protocol.md`

**Step 1: Write the failing test**

新增测试, 锁定以下启动行为:

```python
def test_boot_long_press_button1_runs_pid_identify():
    ...

def test_boot_long_press_button2_runs_calibrate_gyro():
    ...

def test_boot_without_long_press_runs_remote_control_and_exposes_vehicle_role():
    ...
```

同时覆盖 `D8/D9` 角色解码和非法组合的安全失败语义。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_boot_script.py -q`
Expected: FAIL, 原因应为当前 `src/boot.py` 仍用 `D8/D9` 直接切脚本, 尚未支持按钮长按与角色解码。

**Step 3: Write minimal implementation**

将 `src/boot.py` 改为“按钮长按决定脚本入口, `D8/D9` 决定主车/辅车角色”。正常运行路径进入 `script/remote_control.py` 后, 再由运行时读取角色并加载相应 profile。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_boot_script.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/boot.py src/script/remote_control.py docs/Protocol.md tests/unit/services/test_boot_script.py
git commit -m "feat(boot): split role selection from startup entry"
```

### Task 2: 锁定主车/辅车 profile 边界

**Files:**
- Create: `tests/unit/services/test_vehicle_role_profiles.py`
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_diag_mode.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Modify: `docs/developer/strategy.md`

**Step 1: Write the failing test**

新增测试, 锁定以下 profile 行为:

```python
def test_main_vehicle_profile_enables_dual_camera_polling_and_state_machine():
    ...

def test_aux_vehicle_profile_disables_visual_processing_and_keeps_execution_path():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vehicle_role_profiles.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: FAIL, 原因应为当前运行时尚未区分主车/辅车 profile。

**Step 3: Write minimal implementation**

在运行时引入显式主车/辅车 profile。主车 profile 打开双摄轮询和唯一任务状态机, 辅车 profile 关闭视觉处理, 仅保留命令执行与状态回传。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vehicle_role_profiles.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/transport_car.py tests/unit/services/test_vehicle_role_profiles.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_diag_snapshots.py docs/developer/strategy.md
git commit -m "feat(services): add main and auxiliary vehicle profiles"
```

### Task 3: 升级视觉协议为“单次查询, 多条检测响应”

**Files:**
- Modify: `docs/Protocol.md`
- Modify: `src/vision/protocol.py`
- Modify: `src/services/runtime/uart_ingress.py`
- Modify: `tests/unit/services/test_vision_protocol.py`
- Modify: `tests/contract/services/test_transport_runtime_protocol.py`

**Step 1: Write the failing test**

新增测试, 锁定以下协议行为:

```python
def test_single_query_can_return_multiple_detection_messages_for_one_frame():
    ...

def test_protocol_requires_explicit_frame_end_marker():
    ...

def test_non_addressed_camera_stays_silent_on_shared_visual_uart():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: FAIL, 原因应为当前协议只支持单条 `left/top/right/bottom` 单框输入。

**Step 3: Write minimal implementation**

将视觉协议升级为“单次查询对应单个相机当前帧, 允许返回多条检测消息并带显式结束标记”。协议应最少能表达 `camera_id`、`frame_id`、`category` 和 bbox 字段。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/Protocol.md src/vision/protocol.py src/services/runtime/uart_ingress.py tests/unit/services/test_vision_protocol.py tests/contract/services/test_transport_runtime_protocol.py
git commit -m "feat(protocol): support multi-detection responses per query"
```

### Task 4: 引入双摄轮询与观测批次缓存

**Files:**
- Modify: `src/vision/coordinator.py`
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_uart_ingress.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

新增测试, 锁定以下运行时行为:

```python
def test_main_vehicle_polls_cameras_and_builds_observation_batches():
    ...

def test_transport_car_prefers_obstacle_camera_when_poll_budget_is_tight():
    ...

def test_vision_logging_marks_camera_and_frame_boundaries():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_uart_ingress.py tests/unit/services/test_transport_car_logging.py -q`
Expected: FAIL, 原因应为当前运行时只装配单个视觉生产者和单框快照。

**Step 3: Write minimal implementation**

在主车运行时加入双摄轮询调度与批次缓存。每次轮询从单个相机取回当前帧的检测集合, 再交由主车统一筛选、融合并供唯一任务状态机消费。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_uart_ingress.py tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/vision/coordinator.py src/services/transport_car.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_uart_ingress.py tests/unit/services/test_transport_car_logging.py
git commit -m "feat(vision): add dual-camera polling coordinator"
```

### Task 5: 从多检测结果中选择状态机输入并保持主车唯一决策

**Files:**
- Modify: `src/vision/state_machine.py`
- Modify: `src/vision/transforms.py`
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

新增测试, 明确“状态机只消费主车选中的当前目标”, 而不是直接吃全部检测列表:

```python
def test_state_machine_consumes_selected_follower_or_cargo_target_only():
    ...

def test_unselected_detections_do_not_override_active_transport_intent():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL, 原因应为当前状态机仍默认输入就是唯一单框观测。

**Step 3: Write minimal implementation**

在状态机前增加薄选择层, 从当前轮询得到的检测集合里选出“副车对正目标”“搬运物体目标”“避障摘要”等角色化输入。保持状态机仍由主车唯一维护, 不让相机端直接驱动车体动作。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/vision/state_machine.py src/vision/transforms.py src/services/transport_car.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py
git commit -m "feat(vision): select state-machine inputs from detection batches"
```

### Task 6: 完成设备验证与 HIL 留证

**Files:**
- Modify: `tests/hil/README.md`
- Create: `tests/hil/2026-03-dual-camera-polling.md`
- Modify: `docs/developer/tasks.md`

**Step 1: Write the failing test**

本任务不新增 host 自动化失败测试, 改为先补设备验证清单和 HIL 模板, 明确以下留证项:

```text
1. 主车按钮长按入口正确
2. D8/D9 角色识别正确
3. 双摄轮询时未被点名相机严格静默
4. 单次查询多条检测响应可稳定收齐
5. 搬运同时避障时主车仍能稳定驱动辅车
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS, 但设备路径与 HIL 文档尚未补齐, 不能宣称整体验证完成。

**Step 3: Write minimal implementation**

补齐 `stage2 -> stage3 -> HIL` 验证说明, 记录双摄轮询、主车/辅车角色切换、单状态机协同和异常降级观测。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS, 同时 `tests/hil/2026-03-dual-camera-polling.md` 已具备可执行步骤和证据模板。

**Step 5: Commit**

```bash
git add tests/hil/README.md tests/hil/2026-03-dual-camera-polling.md docs/developer/tasks.md
git commit -m "docs(hil): add dual-camera polling verification plan"
```
