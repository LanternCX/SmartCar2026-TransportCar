# 主车 / 辅车最小运行时迁移实施计划

> **给执行代理:** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。步骤使用复选框 `- [ ]` 进行跟踪。

**Goal:** 在保留 `legacy` 稳定性设计基线的前提下, 长出 `src/master` 与 `src/assistant` 两套独立最小运行时, 逐步替代当前统一运行时的职责。

**Architecture:** `src/legacy` 冻结保留原系统完整实现, 既作为稳定性和任务目标基线, 也作为旧系统代码的实际归档位置; `src/master` 与 `src/assistant` 作为两套全新运行时分别实现主车和辅车职责。底盘控制、滤波、运动学、姿态解算等稳定性内核按行为与参数语义保留, 但运行时架构、状态机组织和通信协议外壳允许重写。

**Note:** `src/legacy` 只作为参考, 不再要求保持旧入口可运行; 旧仓库对应测试在归档后应整体退出当前主线验证面。

**Tech Stack:** Python, MicroPython, pytest, UART, 单视觉串口轮询双摄, 最小运动级协同协议

---

## 文件结构

### `src/legacy/`

- `src/legacy/README.md`: 说明 `legacy` 只作为冻结参考基线, 不继续承载新架构演化
- `src/legacy/boot.py`: 原系统启动入口归档
- `src/legacy/config/`: 原系统配置层归档
- `src/legacy/control/`: 原系统控制层归档
- `src/legacy/diagnostics/`: 原系统诊断层归档
- `src/legacy/filters/`: 原系统滤波层归档
- `src/legacy/hardware/`: 原系统硬件驱动归档
- `src/legacy/script/`: 原系统脚本入口归档
- `src/legacy/services/`: 原系统服务编排归档
- `src/legacy/storage/`: 原系统持久化层归档
- `src/legacy/utils/`: 原系统通用工具归档
- `src/legacy/vision/`: 原系统视觉层归档

`src/legacy/` 下保留的是原系统完整实现, 而不是只放说明文档。

### `src/assistant/`

- `src/assistant/__init__.py`: 辅车公开入口
- `src/assistant/main.py`: 辅车启动脚本入口
- `src/assistant/app.py`: 辅车最小应用装配
- `src/assistant/protocol.py`: 主车到辅车的最小运动级协议解析与响应
- `src/assistant/motion_runtime.py`: 辅车底盘执行闭环
- `src/assistant/safety.py`: 急停、超时、停车保护
- `src/assistant/status.py`: 最小状态回报
- `src/assistant/stability/filtering.py`: 辅车滤波内核
- `src/assistant/stability/kinematics.py`: 辅车运动学内核
- `src/assistant/stability/attitude.py`: 辅车姿态解算内核
- `src/assistant/stability/control.py`: 辅车控制内核

### `src/master/`

- `src/master/__init__.py`: 主车公开入口
- `src/master/main.py`: 主车启动脚本入口
- `src/master/app.py`: 主车最小应用装配
- `src/master/protocol.py`: 主车到辅车的运动级下发接口
- `src/master/vision_ingress.py`: 单视觉串口轮询两颗相机的接入与输入组织
- `src/master/vision_state_machine.py`: 简化后的视觉状态机
- `src/master/decision.py`: 主车任务决策与协同输出
- `src/master/motion_runtime.py`: 主车底盘执行闭环
- `src/master/status.py`: 主车最小诊断与状态输出
- `src/master/stability/filtering.py`: 主车滤波内核
- `src/master/stability/kinematics.py`: 主车运动学内核
- `src/master/stability/attitude.py`: 主车姿态解算内核
- `src/master/stability/control.py`: 主车控制内核

### 测试

- `tests/unit/assistant/test_protocol.py`
- `tests/unit/assistant/test_safety.py`
- `tests/unit/assistant/test_motion_runtime.py`
- `tests/unit/assistant/test_app.py`
- `tests/unit/master/test_vision_ingress.py`
- `tests/unit/master/test_vision_state_machine.py`
- `tests/unit/master/test_decision.py`
- `tests/unit/master/test_motion_runtime.py`
- `tests/unit/master/test_stability_baseline.py`
- `tests/unit/master/test_app.py`
- `tests/unit/assistant/test_stability_baseline.py`
- `tests/contract/master_assistant/test_motion_protocol.py`
- `tests/hil/2026-03-assistant-minimal-runtime.md`
- `tests/hil/2026-03-master-minimal-runtime.md`
- `tests/hil/2026-03-master-assistant-protocol.md`

---

### Task 1: 真实归档旧系统到 `src/legacy`

**Files:**
- Create: `src/legacy/README.md`
- Move: `src/boot.py -> src/legacy/boot.py`
- Move: `src/config/ -> src/legacy/config/`
- Move: `src/control/ -> src/legacy/control/`
- Move: `src/diagnostics/ -> src/legacy/diagnostics/`
- Move: `src/filters/ -> src/legacy/filters/`
- Move: `src/hardware/ -> src/legacy/hardware/`
- Move: `src/script/ -> src/legacy/script/`
- Move: `src/services/ -> src/legacy/services/`
- Move: `src/storage/ -> src/legacy/storage/`
- Move: `src/utils/ -> src/legacy/utils/`
- Move: `src/vision/ -> src/legacy/vision/`
- Create: `tests/unit/legacy/test_archive_layout.py`

- [ ] **Step 1: 先为 `legacy` 实际归档写失败测试**

```python
def test_legacy_tree_contains_original_runtime_roots() -> None:
    from pathlib import Path

    root = Path("src/legacy")
    assert (root / "services").exists()
    assert (root / "vision").exists()
    assert (root / "control").exists()


def test_src_root_is_reduced_to_legacy_master_assistant() -> None:
    from pathlib import Path

    src_root = Path("src")
    assert not (src_root / "services").exists()
    assert not (src_root / "vision").exists()
    assert not (src_root / "control").exists()
    assert (src_root / "legacy").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/legacy/test_archive_layout.py -q`
Expected: FAIL, 因 `legacy` 实际归档尚未完成

- [ ] **Step 3: 先完成旧系统真实归档**

并在 `src/legacy/README.md` 说明:

- `legacy` 只作为冻结参考基线
- `legacy` 是旧系统代码的实际归档位置
- 新系统不得从 `legacy` 直接导入运行时依赖

并完成以下目录调整:

- 将旧系统主干运行时代码从 `src` 根下移入 `src/legacy`
- 让 `src` 根下结构开始收敛到 `legacy / master / assistant`

- [ ] **Step 4: 先验证目录已真实收敛**

Run: `python3 -m pytest tests/unit/legacy/test_archive_layout.py -q`
Expected: PASS

> 阻断门禁: 在本步通过前, 不得继续创建或扩张 `src/master` / `src/assistant` 的运行时代码

- [ ] **Step 5: 若用户要求提交再处理 commit**

提交前先向用户确认 commit message, 不得自行 commit

---

### Task 2: 实现辅车最小执行闭环

**Files:**
- Create: `docs/developer/legacy-stability-baseline.md`
- Create: `src/assistant/__init__.py`
- Create: `src/assistant/main.py`
- Modify: `src/assistant/app.py`
- Create: `src/assistant/protocol.py`
- Create: `src/assistant/motion_runtime.py`
- Create: `src/assistant/safety.py`
- Create: `src/assistant/status.py`
- Create: `src/assistant/stability/filtering.py`
- Create: `src/assistant/stability/kinematics.py`
- Create: `src/assistant/stability/attitude.py`
- Create: `src/assistant/stability/control.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_safety.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_app.py`
- Create: `tests/hil/2026-03-assistant-minimal-runtime.md`

- [ ] **Step 1: 写失败测试**

```python
def test_assistant_protocol_parses_move_command() -> None:
    from assistant.protocol import parse_command
    result = parse_command("MOVE 0.10 -0.05 15")
    assert result.kind == "move"
    assert result.dx == 0.10
    assert result.dy == -0.05
    assert result.dtheta == 15.0


def test_assistant_safety_triggers_stop_on_timeout() -> None:
    from assistant.safety import SafetyGuard
    guard = SafetyGuard(timeout_ms=100)
    guard.mark_command(0)
    assert guard.should_stop(150) is True


def test_assistant_stability_baseline_keeps_attitude_and_kinematics_contract() -> None:
    from assistant.stability.kinematics import body_axis_semantics
    from assistant.stability.attitude import euler_to_quaternion, quaternion_to_euler

    semantics = body_axis_semantics()
    assert semantics["x_positive"] == "right"
    assert semantics["y_positive"] == "forward"
    quat = euler_to_quaternion(0.0, 0.0, 10.0)
    yaw_deg = quaternion_to_euler(quat)[2]
    assert abs(yaw_deg - 10.0) < 1e-3


def test_assistant_app_module_imports() -> None:
    from assistant.app import AssistantApp
    assert AssistantApp is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_protocol.py tests/unit/assistant/test_safety.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_app.py -q`
Expected: FAIL, 因辅车最小执行链尚未建立

- [ ] **Step 3: 写最小实现**

```python
class SafetyGuard:
    def __init__(self, timeout_ms: int):
        self.timeout_ms = int(timeout_ms)
        self.last_command_ms = None

    def mark_command(self, now_ms: int) -> None:
        self.last_command_ms = int(now_ms)

    def should_stop(self, now_ms: int) -> bool:
        if self.last_command_ms is None:
            return False
        return int(now_ms) - self.last_command_ms >= self.timeout_ms
```

并在 `assistant` 中完成以下最小能力:

- 先在 `docs/developer/legacy-stability-baseline.md` 写清从 `legacy` 继承的稳定性基线:
  - 底盘控制语义
  - 滤波链语义
  - 运动学语义
  - 陀螺仪 / 四元数 / 欧拉角语义
  - 关键方向 / 符号约定
  - 关键参数语义
  - 对应到 `assistant` 最小系统的验证点与验证命令
- 解析 `ARM` / `DISARM` / `STOP` / `PING` / `STATE?`
- 解析 `VEL` / `MOVE` / `HOLD` / `RESET_ODOM`
- 维持一个最小执行状态
- 提供超时停机和急停保护
- 使用从 `legacy` 提炼出的控制 / 滤波 / 运动学 / 姿态解算行为基线

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_protocol.py tests/unit/assistant/test_safety.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_app.py -q`
Expected: PASS

- [ ] **Step 5: 记录设备侧 smoke 与 HIL 留证**

Run: `python3 tools/run_stage2_smoke.py --port <port>`
Expected: 至少拿到 assistant 最小运行时可连接、可导入、可响应最小协议的 stage2 证据

并在 `tests/hil/2026-03-assistant-minimal-runtime.md` 记录:

- 操作步骤
- 预期行为
- 实测输出
- PASS / FAIL

- [ ] **Step 6: 若用户要求提交再处理 commit**

提交前先向用户确认 commit message, 不得自行 commit

---

### Task 3: 实现主车双摄轮询输入与简化视觉状态机

**Files:**
- Create: `src/master/__init__.py`
- Create: `src/master/main.py`
- Modify: `src/master/app.py`
- Create: `src/master/protocol.py`
- Create: `src/master/vision_ingress.py`
- Create: `src/master/vision_state_machine.py`
- Create: `src/master/decision.py`
- Create: `src/master/motion_runtime.py`
- Create: `src/master/status.py`
- Create: `src/master/stability/filtering.py`
- Create: `src/master/stability/kinematics.py`
- Create: `src/master/stability/attitude.py`
- Create: `src/master/stability/control.py`
- Test: `tests/unit/master/test_stability_baseline.py`
- Test: `tests/unit/master/test_vision_ingress.py`
- Test: `tests/unit/master/test_vision_state_machine.py`
- Test: `tests/unit/master/test_decision.py`
- Test: `tests/unit/master/test_motion_runtime.py`
- Test: `tests/unit/master/test_app.py`
- Create: `tests/hil/2026-03-master-minimal-runtime.md`

- [ ] **Step 1: 写失败测试**

```python
def test_master_vision_ingress_keeps_single_uart_polling_topology() -> None:
    from master.vision_ingress import VisionIngress
    ingress = VisionIngress(vision_uart="uart6", camera_ids=("cam_a", "cam_b"))
    assert ingress.vision_uart == "uart6"
    assert ingress.camera_ids == ("cam_a", "cam_b")


def test_master_vision_state_machine_outputs_motion_target() -> None:
    from master.vision_state_machine import VisionStateMachine
    machine = VisionStateMachine()
    target = machine.step(observation={"target": "box"})
    assert target is not None


def test_master_stability_baseline_keeps_attitude_and_kinematics_contract() -> None:
    from master.stability.kinematics import body_axis_semantics
    from master.stability.attitude import euler_to_quaternion, quaternion_to_euler

    semantics = body_axis_semantics()
    assert semantics["x_positive"] == "right"
    assert semantics["y_positive"] == "forward"
    quat = euler_to_quaternion(0.0, 0.0, 10.0)
    yaw_deg = quaternion_to_euler(quat)[2]
    assert abs(yaw_deg - 10.0) < 1e-3


def test_master_app_module_imports() -> None:
    from master.app import MasterApp
    assert MasterApp is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py -q`
Expected: FAIL, 因主车最小视觉链和决策链尚未建立

- [ ] **Step 3: 写最小实现**

```python
class VisionIngress:
    def __init__(self, vision_uart, camera_ids):
        self.vision_uart = vision_uart
        self.camera_ids = tuple(camera_ids)
```

并完成以下最小职责:

- 保留“单视觉串口轮询两颗相机”的输入拓扑
- 保留目标选择
- 保留简化后的视觉状态机
- 输出主车自身运动目标与辅车运动命令
- 使用从 `legacy` 提炼出的控制 / 滤波 / 运动学 / 姿态解算行为基线
- 用 `docs/developer/legacy-stability-baseline.md` 中的语义清单核对主车稳定性实现

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py -q`
Expected: PASS

- [ ] **Step 5: 记录设备侧 smoke 与 HIL 留证**

Run: `python3 tools/run_stage2_smoke.py --port <port>`
Expected: 至少拿到 master 最小运行时可连接、可导入、可轮询双摄输入、可执行简化状态机的 stage2 证据

并在 `tests/hil/2026-03-master-minimal-runtime.md` 记录:

- 操作步骤
- 预期行为
- 实测输出
- PASS / FAIL

- [ ] **Step 6: 若用户要求提交再处理 commit**

提交前先向用户确认 commit message, 不得自行 commit

---

### Task 4: 打通主辅车最小运动级协议契约

**Files:**
- Modify: `src/master/protocol.py`
- Modify: `src/master/decision.py`
- Modify: `src/assistant/protocol.py`
- Modify: `src/assistant/status.py`
- Test: `tests/contract/master_assistant/test_motion_protocol.py`
- Create: `tests/hil/2026-03-master-assistant-protocol.md`

- [ ] **Step 1: 写失败测试**

```python
def test_master_assistant_motion_protocol_contract() -> None:
    from master.protocol import build_move_command
    from assistant.protocol import parse_command
    command = build_move_command(dx=0.10, dy=0.0, dtheta=15.0)
    parsed = parse_command(command)
    assert parsed.kind == "move"
    assert parsed.dx == 0.10
    assert parsed.dy == 0.0
    assert parsed.dtheta == 15.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: FAIL, 因主辅车协议契约尚未打通

- [ ] **Step 3: 写最小实现**

```python
def build_move_command(dx: float, dy: float, dtheta: float) -> str:
    return "MOVE %.3f %.3f %.3f" % (dx, dy, dtheta)
```

并保证辅车最小状态回报只包含:

- `ACK`
- `BUSY`
- `DONE`
- `ERR`
- `STATE`

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS

- [ ] **Step 5: 运行阶段性聚合验证**

Run: `python3 -m pytest tests/unit/master tests/unit/assistant tests/contract/master_assistant -q`
Expected: PASS

- [ ] **Step 6: 补主辅协同设备留证**

在 `tests/hil/2026-03-master-assistant-protocol.md` 中记录主辅联调留证, 至少包含:

- 主车下发最小运动命令
- 辅车正确执行并回报 `ACK/BUSY/DONE/STATE`
- 失败归因

- [ ] **Step 7: 若用户要求提交再处理 commit**

提交前先向用户确认 commit message, 不得自行 commit

---

### Task 5: 制定旧系统裁剪清单并冻结删除顺序

**Files:**
- Create: `docs/developer/legacy-pruning-checklist.md`

- [ ] **Step 1: 写裁剪清单**

明确以下 3 类内容:

- 必须迁移到 `master` / `assistant` 的稳定性内核
- 只在 `legacy` 中保留、不进入新系统的旧结构
- 等新系统跑通后可归档的旧查询面、兼容层和非核心功能

- [ ] **Step 2: 审核清单是否与 spec 一致**

Run: 人工逐项对照 `docs/superpowers/specs/2026-03-24-master-assistant-minimal-runtime-design.md`
Expected: 不出现“为了结构好看而删除完赛关键能力”的条目

- [ ] **Step 3: 若用户要求提交再处理 commit**

提交前先向用户确认 commit message, 不得自行 commit
