# Transport 运行时完整解耦 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在保持串口协议, 查询格式, 视觉吞包语义和控制时序不变的前提下, 完整解耦 `TransportCar`, 并将视觉子系统迁移到独立 `src/vision/` 包。

**Architecture:** 先用 contract/unit/HIL 保护网锁住外部行为, 再按状态所有权重构为 `CommandSession`、`ChassisController`、`VisionCoordinator`、`UartIngressService` 和 `DiagnosticsFacade`。`TransportCar` 最终只保留整车装配与主循环调度职责, 不再持有命令协议细节和视觉内部状态。

**Tech Stack:** Python, pytest unit/contract tests, MicroPython compatibility checks, Stage 2 smoke, Stage 3 uart observe, HIL evidence.

---

### Task 1: 锁定外部协议与运行时行为保护网

**Files:**
- Create: `tests/contract/services/test_transport_runtime_protocol.py`
- Modify: `tests/contract/services/commands/test_motion_commands.py`
- Modify: `tests/contract/services/commands/test_reset_query_commands.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_vision_protocol.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`

**Step 1: Write the failing test**

新增或补齐以下黑盒断言：

```python
def test_uart6_visual_frame_is_consumed_before_command_routing():
    ...

def test_query_replies_to_original_uart_source():
    ...

def test_rear_mode_change_locks_and_auto_reverts_after_completion():
    ...
```

重点锁住 `UART6` 视觉吞包, query 原串口回包, `reset` 裸命令, `rear` 自动回退, tick 时序和视觉优先级。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_motion_commands.py tests/contract/services/commands/test_reset_query_commands.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: FAIL, 原因应为新契约尚未被现有测试或实现完整覆盖。

**Step 3: Write minimal implementation**

仅在必要处补齐当前行为保护测试, 不先做结构重构。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_motion_commands.py tests/contract/services/commands/test_reset_query_commands.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_motion_commands.py tests/contract/services/commands/test_reset_query_commands.py tests/contract/services/test_transport_runtime_protocol.py
git commit -m "test(services): lock transport runtime behavior"
```

### Task 2: 创建 vision 独立包并迁移纯视觉模块

**Files:**
- Create: `src/vision/__init__.py`
- Create: `src/vision/protocol.py`
- Create: `src/vision/state_defs.py`
- Create: `src/vision/state_registry.py`
- Create: `src/vision/state_machine.py`
- Create: `src/vision/transforms.py`
- Create: `src/vision/debug.py`
- Modify: `tests/unit/services/test_vision_protocol.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`
- Modify: `tests/unit/services/test_vision_control_adapter.py`
- Modify: `tests/unit/services/test_vision_state_registry.py`
- Modify: `tests/unit/services/test_micropython_compatibility.py`

**Step 1: Write the failing test**

先将纯视觉相关测试导入路径切换到 `vision.*`：

```python
from vision.protocol import VisionProtocol
from vision.state_machine import VisionStateMachine
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_vision_control_adapter.py tests/unit/services/test_vision_state_registry.py tests/unit/services/test_micropython_compatibility.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'vision'`.

**Step 3: Write minimal implementation**

将现有 `services/vision_*.py` 的实现整体迁入 `src/vision/`。拆分 `normalize_angle` 和相对意图转换逻辑到 `src/vision/transforms.py`, 保持算法和输出完全不变。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_vision_control_adapter.py tests/unit/services/test_vision_state_registry.py tests/unit/services/test_micropython_compatibility.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/vision tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_vision_control_adapter.py tests/unit/services/test_vision_state_registry.py tests/unit/services/test_micropython_compatibility.py
git commit -m "refactor(vision): move vision modules into dedicated package"
```

### Task 3: 引入 CommandSession 与显式 handler 上下文

**Files:**
- Create: `src/services/commanding/__init__.py`
- Create: `src/services/commanding/router.py`
- Create: `src/services/commanding/session.py`
- Create: `src/services/commanding/context.py`
- Create: `src/services/commanding/handlers/__init__.py`
- Create: `src/services/commanding/handlers/cmd_*.py`
- Create: `src/services/commanding/handlers/query_*.py`
- Modify: `tests/unit/services/test_command_router.py`
- Modify: `tests/contract/services/commands/test_motion_commands.py`
- Modify: `tests/contract/services/commands/test_reset_query_commands.py`
- Modify: `tests/fakes/fake_context.py`

**Step 1: Write the failing test**

新增测试, 明确 handler 只能调用显式接口, 不再写宿主私有字段：

```python
def test_relative_command_handlers_use_session_api_instead_of_private_fields():
    ...

def test_query_handlers_do_not_depend_on_transport_private_state():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_command_router.py tests/contract/services/commands/test_motion_commands.py tests/contract/services/commands/test_reset_query_commands.py -q`
Expected: FAIL, 原因应为当前 handler 仍直接依赖宿主对象内部字段和临时上下文字段。

**Step 3: Write minimal implementation**

引入 `CommandSession` 作为命令状态唯一拥有者, 将 `last_cmd`、lock、相对位移、rear 和 reset 语义收口到 session 中。调整 router 和 handlers 只依赖显式上下文接口。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_command_router.py tests/contract/services/commands/test_motion_commands.py tests/contract/services/commands/test_reset_query_commands.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/commanding tests/unit/services/test_command_router.py tests/contract/services/commands/test_motion_commands.py tests/contract/services/commands/test_reset_query_commands.py tests/fakes/fake_context.py
git commit -m "refactor(services): extract command session and explicit handler context"
```

### Task 4: 将底盘运行态和控制栈下沉到 control 层

**Files:**
- Create: `src/control/chassis_state.py`
- Create: `src/control/attitude_estimator.py`
- Create: `src/control/wheel_speed_controller.py`
- Create: `src/control/motion_planner.py`
- Create: `src/control/chassis_controller.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Create: `tests/unit/control/test_chassis_controller.py`
- Create: `tests/unit/control/test_motion_planner.py`

**Step 1: Write the failing test**

新增底盘控制黑盒和子模块单测：

```python
def test_chassis_controller_preserves_tick_order_and_updates_outputs():
    ...

def test_motion_planner_preserves_position_and_velocity_mode_semantics():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/control/test_chassis_controller.py tests/unit/control/test_motion_planner.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL, 原因应为新控制对象尚不存在。

**Step 3: Write minimal implementation**

将轮速滤波, 姿态更新, 里程计, 位置/角度控制, rear 模式目标分配, 解锁判定迁移到 `control` 新对象内, 但保持算法公式和控制顺序不变。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/control/test_chassis_controller.py tests/unit/control/test_motion_planner.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/control/chassis_state.py src/control/attitude_estimator.py src/control/wheel_speed_controller.py src/control/motion_planner.py src/control/chassis_controller.py tests/unit/control/test_chassis_controller.py tests/unit/control/test_motion_planner.py tests/unit/services/test_transport_car_vision_integration.py
git commit -m "refactor(control): extract chassis control stack"
```

### Task 5: 引入 VisionCoordinator 和 UartIngressService

**Files:**
- Create: `src/vision/coordinator.py`
- Create: `src/services/runtime/uart_ingress.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/contract/services/test_transport_runtime_protocol.py`
- Create: `tests/unit/services/test_uart_ingress.py`

**Step 1: Write the failing test**

新增测试, 锁住 `uart6` 视觉优先消费和 `uart3`/`uart6` 分路行为：

```python
def test_uart_ingress_routes_visual_query_and_command_lines_to_correct_subsystem():
    ...

def test_vision_coordinator_resets_observation_when_manual_lock_is_active():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_uart_ingress.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: FAIL, 原因应为新的接入与协调对象尚不存在。

**Step 3: Write minimal implementation**

引入 `VisionCoordinator` 封装视觉观测, 状态机和视觉目标, 引入 `UartIngressService` 统一收包, 分行, source 判定和错误日志处理。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_uart_ingress.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/vision/coordinator.py src/services/runtime/uart_ingress.py tests/unit/services/test_uart_ingress.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/test_transport_runtime_protocol.py
git commit -m "refactor(services): extract uart ingress and vision coordinator"
```

### Task 6: 引入 DiagnosticsFacade 并重写 query 链路

**Files:**
- Create: `src/services/runtime/diagnostics_facade.py`
- Modify: `src/services/diagnostics.py`
- Modify: `tests/contract/services/commands/test_diag_queries.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`

**Step 1: Write the failing test**

新增测试确保 query handler 只通过 façade 提供的数据工作：

```python
def test_diagnostics_facade_preserves_snapshot_keys_and_query_format():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/services/commands/test_diag_queries.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: FAIL, 原因应为新的 façade 尚不存在。

**Step 3: Write minimal implementation**

引入 `DiagnosticsFacade`, 统一聚合 health/tick/imu/enc/motor/vision/pos/lock 数据, 并确保 query 输出格式保持不变。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/services/commands/test_diag_queries.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/runtime/diagnostics_facade.py src/services/diagnostics.py tests/contract/services/commands/test_diag_queries.py tests/unit/services/test_transport_car_diag_snapshots.py
git commit -m "refactor(services): extract diagnostics facade"
```

### Task 7: 将 `TransportCar` 收缩为装配与调度入口

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_diag_mode.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`

**Step 1: Write the failing test**

新增断言, 确保 `TransportCar` 只通过子系统协作而非内部私有字段工作：

```python
def test_transport_car_composes_subsystems_without_owning_command_or_vision_private_state():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: FAIL, 原因应为 `TransportCar` 仍持有旧私有状态和旧方法。

**Step 3: Write minimal implementation**

删除 `TransportCar` 中旧的命令暂存字段, query 临时字段和视觉内部状态, 改为只装配和调度子系统。清理废弃方法和旧调用链。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/transport_car.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_diag_snapshots.py
git commit -m "refactor(services): reduce transport car to runtime composition root"
```

### Task 8: 删除旧路径和遗留结构

**Files:**
- Delete: `src/services/vision_debug.py`
- Delete: `src/services/vision_protocol.py`
- Delete: `src/services/vision_state_defs.py`
- Delete: `src/services/vision_state_machine.py`
- Delete: `src/services/vision_state_registry.py`
- Delete: `src/services/command_router.py`
- Delete: `src/services/commands/`
- Delete: `src/services/commander.py`

**Step 1: Write the failing test**

先将剩余引用和测试全部切换到新路径, 确保任何旧路径引用都会在测试中暴露。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: FAIL, 原因应为仓库中仍存在旧导入或旧路径依赖。

**Step 3: Write minimal implementation**

删除所有旧路径, 清理导入, 保证仓库最终只剩新架构路径, 不保留兼容壳。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services src/vision tests/unit tests/contract
git commit -m "refactor(services): remove legacy transport runtime structure"
```

### Task 9: 执行设备验证并补 HIL 证据

**Files:**
- Modify: `tests/hil/README.md`
- Modify: `tests/hil/scenarios/basic_motion.md`
- Modify: `tests/hil/scenarios/vision_bbox_alignment.md`
- Create: `tests/hil/scenarios/transport_runtime_decoupling.md`

**Step 1: Stage 2 smoke**

Run: `python3 tools/run_stage2_smoke.py --port <PORT>`
Expected: `status=ok`, query 链路和最小运行正常。

**Step 2: Stage 3 observe**

通过 `uart3` 记录以下观测：

- `?health/?tick/?imu/?enc/?motor/?vision/?lock/?pos`
- `uart6` 连续视觉流与 `uart3` 查询并发
- `reset` 打断视觉推行链路

Expected: 行为与重构前一致, 无额外 overrun 和串口语义漂移。

**Step 3: Write HIL evidence**

将操作步骤, 预期行为, 实际输出和 PASS/FAIL 写入 `tests/hil/scenarios/transport_runtime_decoupling.md`。

**Step 4: Commit**

```bash
git add tests/hil/README.md tests/hil/scenarios/basic_motion.md tests/hil/scenarios/vision_bbox_alignment.md tests/hil/scenarios/transport_runtime_decoupling.md
git commit -m "test(hil): add transport runtime decoupling evidence"
```

### Task 10: 最终验证与收尾

**Files:**
- Verify only

**Step 1: Run host suite**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 2: Run compatibility check**

Run: `python3 -m pytest tests/unit/services/test_micropython_compatibility.py -q`
Expected: PASS.

**Step 3: Inspect worktree**

Run: `git status --short`
Expected: 仅出现本次重构相关新增/修改/删除文件, 不保留旧路径兼容层。

**Step 4: Report evidence**

汇总：目录重构结果, 行为保护验证, Stage 2 / Stage 3 / HIL 证据和 remaining risk。
