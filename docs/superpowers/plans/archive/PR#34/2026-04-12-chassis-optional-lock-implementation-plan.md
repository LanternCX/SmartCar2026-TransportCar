# 当前底盘协议可选 `lock` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来执行本计划。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 在不改视觉仓库的前提下, 为当前底盘协议中的原锁定命令增加可选 `lock` 语义, 同时补齐可观察的执行方式诊断。

**Architecture:** 先把“可选 `lock` + 新命令抢占 + `command_mode` 诊断”锁进主机侧纯 Python 测试, 再把路由后处理逻辑从 `TransportCar` 中抽到一个不依赖硬件模块的服务层辅助文件, 让命令处理和诊断字段都能在主机侧验证。运行时入口、运动学、视觉状态机和视觉仓库边界保持不动, 只同步当前仓库的协议与开发文档口径。

**Tech Stack:** Python 3.8+ 主机侧 `pytest`, RT1021 MicroPython 运行时, `src/services/command_router.py`, `src/services/transport_car.py`

**Git Note:** 本仓库提交前必须先向用户确认提交消息, 因此本计划不包含自动提交步骤。

---

## 文件边界

- Create: `src/services/command_policy.py`
- Create: `src/services/commands/cmd_lock.py`
- Create: `tests/unit/test_optional_lock_commands.py`
- Create: `tests/contract/test_optional_lock_protocol_doc_contract.py`
- Modify: `src/services/transport_car.py`
- Modify: `src/services/stage2_smoke.py`
- Modify: `src/services/commands/cmd_x.py`
- Modify: `src/services/commands/cmd_y.py`
- Modify: `src/services/commands/cmd_angle.py`
- Modify: `src/services/commands/cmd_dx.py`
- Modify: `src/services/commands/cmd_dy.py`
- Modify: `src/services/commands/cmd_d_angle.py`
- Modify: `src/services/commands/cmd_rear.py`
- Modify: `src/services/commands/cmd_vx.py`
- Modify: `src/services/commands/cmd_vy.py`
- Modify: `src/services/commands/cmd_omega.py`
- Modify: `src/services/commands/cmd_reset.py`
- Modify: `.agents/skills/using-rules/references/openart-protocol.md`
- Modify: `docs/developer/control.md`

### Task 1: 先用主机侧测试锁住可选 `lock` 行为

**Files:**
- Create: `tests/unit/test_optional_lock_commands.py`
- Create: `src/services/command_policy.py`

- [ ] **Step 1: 写出会先失败的纯逻辑测试文件**

```python
"""可选 lock 命令语义测试."""

import services.commands as _commands  # noqa: F401 触发命令注册

from services.command_router import router
from services.command_policy import build_command_health_fields, finalize_command_route


class _CaptureUart:
    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class _Odom:
    def __init__(self, x=1.0, y=2.0):
        self.x = float(x)
        self.y = float(y)


class _RouteContext:
    def __init__(self):
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.command_mode = "none"
        self.lock_start_time = 0
        self.rear_only_mode = False
        self.last_rear_mode = False
        self._rear_mode_changed = False
        self._pending_dx = None
        self._pending_dy = None
        self._pending_d_angle = None
        self._pending_lock = None
        self.heading_est = 0.0
        self.heading_target = 0.0
        self.odometry = _Odom()
        self.uart3 = _CaptureUart()

    def _get_active_rear_only_mode(self):
        return self.rear_only_mode

    def _finalize_route(self, dispatched):
        finalize_command_route(self, dispatched, now_ms=4321)


def test_lock_zero_keeps_relative_command_unlocked() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,dy=-0.20,lock=0", ctx) is True

    assert ctx.command_lock is False
    assert ctx.command_mode == "unlocked"
    assert ctx.last_cmd["x"] == 1.10
    assert ctx.last_cmd["y"] == 1.80


def test_lock_one_sets_locked_mode_and_resets_lock_timer() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,lock=1", ctx) is True

    assert ctx.command_lock is True
    assert ctx.command_mode == "locked"
    assert ctx.lock_start_time == 4321


def test_new_unlocked_packet_preempts_previous_locked_target() -> None:
    ctx = _RouteContext()
    assert router.route("dx=0.10,lock=1", ctx) is True

    assert router.route("dx=-0.05,dy=0.04,lock=0", ctx) is True

    assert ctx.command_lock is False
    assert ctx.command_mode == "unlocked"
    assert ctx.last_cmd["x"] == 0.95
    assert ctx.last_cmd["y"] == 2.04


def test_rear_and_relative_move_share_same_lock_zero_packet() -> None:
    ctx = _RouteContext()

    assert router.route("rear=1,dx=0.02,dy=0.03,lock=0", ctx) is True

    assert ctx.rear_only_mode is True
    assert ctx.command_mode == "unlocked"


def test_velocity_packet_clears_position_targets_and_exits_command_mode() -> None:
    ctx = _RouteContext()
    assert router.route("dx=0.10,dy=0.10,lock=0", ctx) is True

    assert router.route("vy=12", ctx) is True

    assert "x" not in ctx.last_cmd
    assert "y" not in ctx.last_cmd
    assert ctx.last_cmd["vy"] == 12.0
    assert ctx.command_mode == "none"


def test_health_fields_include_command_mode() -> None:
    ctx = _RouteContext()
    ctx.command_lock = False
    ctx.command_mode = "unlocked"
    ctx.rear_only_mode = True

    assert build_command_health_fields(ctx) == {
        "lock": 0,
        "rear": 1,
        "command_mode": "unlocked",
    }
```

- [ ] **Step 2: 运行测试并确认它先失败**

Run: `python3 -m pytest tests/unit/test_optional_lock_commands.py -q`
Expected: FAIL, 原因应直接指向 `services.command_policy` 尚不存在, 或当前路由仍不支持 `lock` / 抢占 / `command_mode`。

- [ ] **Step 3: 确认测试边界只锁本轮需求**

```python
def test_velocity_packet_clears_position_targets_and_exits_command_mode() -> None:
    ctx = _RouteContext()
    assert router.route("dx=0.10,dy=0.10,lock=0", ctx) is True

    assert router.route("vy=12", ctx) is True

    assert "x" not in ctx.last_cmd
    assert "y" not in ctx.last_cmd
    assert ctx.last_cmd["vy"] == 12.0
    assert ctx.command_mode == "none"
```

这一步只保留本轮需要的六条事实：`lock=0`、`lock=1`、新命令抢占、`rear` 组合、速度命令退出位置目标、健康字段包含 `command_mode`。不要把视觉仓库、串口来源分流或板端超时逻辑混进测试。

### Task 2: 实现纯逻辑辅助文件并接入当前命令链

**Files:**
- Create: `src/services/command_policy.py`
- Create: `src/services/commands/cmd_lock.py`
- Modify: `src/services/transport_car.py`
- Modify: `src/services/stage2_smoke.py`
- Modify: `src/services/commands/cmd_x.py`
- Modify: `src/services/commands/cmd_y.py`
- Modify: `src/services/commands/cmd_angle.py`
- Modify: `src/services/commands/cmd_dx.py`
- Modify: `src/services/commands/cmd_dy.py`
- Modify: `src/services/commands/cmd_d_angle.py`
- Modify: `src/services/commands/cmd_rear.py`
- Modify: `src/services/commands/cmd_vx.py`
- Modify: `src/services/commands/cmd_vy.py`
- Modify: `src/services/commands/cmd_omega.py`
- Modify: `src/services/commands/cmd_reset.py`

- [ ] **Step 1: 创建纯 Python 的命令策略辅助文件**

```python
"""命令锁语义与执行方式辅助函数."""

import math


LOCKABLE_COMMAND_KEYS = {
    "x",
    "y",
    "angle",
    "yaw",
    "dx",
    "dy",
    "d_angle",
    "dyaw",
    "da",
    "rear",
}
PLANAR_SPEED_KEYS = {"vx", "vy"}
ANGULAR_SPEED_KEYS = {"omega", "w"}


def build_command_health_fields(ctx):
    rear_only_mode = (
        ctx._get_active_rear_only_mode()
        if hasattr(ctx, "_get_active_rear_only_mode")
        else getattr(ctx, "rear_only_mode", False)
    )
    return {
        "lock": 1 if getattr(ctx, "command_lock", False) else 0,
        "rear": 1 if rear_only_mode else 0,
        "command_mode": getattr(ctx, "command_mode", "none"),
    }


def finalize_command_route(ctx, dispatched, now_ms):
    if "reset" in dispatched:
        ctx._pending_lock = None
        ctx.command_mode = "none"
        return

    pending_lock = getattr(ctx, "_pending_lock", None)
    ctx._pending_lock = None

    has_lockable = any(key in dispatched for key in LOCKABLE_COMMAND_KEYS)
    has_planar_speed = any(key in dispatched for key in PLANAR_SPEED_KEYS)
    has_angular_speed = any(key in dispatched for key in ANGULAR_SPEED_KEYS)

    if getattr(ctx, "_pending_d_angle", None) is not None:
        ctx.last_cmd["angle"] = ctx.heading_target + ctx._pending_d_angle
        ctx.last_cmd.pop("omega", None)
        ctx._pending_d_angle = None
        has_lockable = True

    if getattr(ctx, "_pending_dx", None) is not None or getattr(ctx, "_pending_dy", None) is not None:
        dx_body = ctx._pending_dx if ctx._pending_dx is not None else 0.0
        dy_body = ctx._pending_dy if ctx._pending_dy is not None else 0.0
        theta_rad = math.radians(ctx.heading_est)
        cos_t = math.cos(theta_rad)
        sin_t = math.sin(theta_rad)
        ctx.last_cmd["x"] = ctx.odometry.x + dx_body * cos_t - dy_body * sin_t
        ctx.last_cmd["y"] = ctx.odometry.y + dx_body * sin_t + dy_body * cos_t
        ctx.last_cmd.pop("vx", None)
        ctx.last_cmd.pop("vy", None)
        ctx._pending_dx = None
        ctx._pending_dy = None
        has_lockable = True

    if has_planar_speed:
        ctx.last_cmd.pop("x", None)
        ctx.last_cmd.pop("y", None)
    if has_angular_speed:
        ctx.last_cmd.pop("angle", None)

    rear_mode_changed = getattr(ctx, "_rear_mode_changed", False)
    ctx._rear_mode_changed = False

    if has_lockable or rear_mode_changed:
        use_lock = True if pending_lock is None else bool(pending_lock)
        ctx.command_lock = use_lock
        ctx.command_mode = "locked" if use_lock else "unlocked"
        if use_lock:
            ctx.lock_start_time = int(now_ms)
    elif has_planar_speed or has_angular_speed:
        ctx.command_lock = False
        ctx.command_mode = "none"
```

- [ ] **Step 2: 新增 `lock` 命令处理器并让旧命令不再因为旧锁直接丢弃**

```python
"""lock 执行方式指令处理器."""

from services.command_router import router


@router.command("lock")
def handle(ctx, value):
    """记录当前整包命令是否要求等待完成."""
    ctx._pending_lock = value != 0
```

```python
@router.command("dx")
def handle(ctx, value):
    ctx._pending_dx = value


@router.command("rear")
def handle(ctx, value):
    new_mode = value != 0
    ctx._rear_mode_changed = new_mode != ctx.rear_only_mode
    ctx.rear_only_mode = new_mode
    ctx.uart3.write("Rear Only Mode: %s\r\n" % str(ctx.rear_only_mode))


@router.command("vy")
def handle(ctx, value):
    ctx.last_cmd["vy"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
```

这里的关键点不是重命名命令, 而是删除原来依赖 `ctx.command_lock` 的早退, 让“新命令总是抢占旧命令”的规则真正有机会落地。

- [ ] **Step 3: 把 `TransportCar` 的后处理和健康快照切到新辅助文件**

```python
from services.command_policy import build_command_health_fields, finalize_command_route


class TransportCar:
    def __init__(self, diagnostic_mode=False):
        ...
        self.command_lock = False
        self.command_mode = "none"
        ...
        self._pending_lock = None

    def build_health_snapshot(self):
        snapshot = {
            "alive": 1,
            "uptime_ms": max(0, self._now_ms() - int(self.boot_time_ms)),
            "last_err": self.last_exception_text,
            "vision_state": self._get_vision_state_name(),
        }
        snapshot.update(build_command_health_fields(self))
        return snapshot

    def _finalize_route(self, dispatched):
        finalize_command_route(self, dispatched, now_ms=self._now_ms())

    def _check_unlock(self):
        ...
        if angle_ok and pos_ok:
            self.command_lock = False
            self.command_mode = "none"
            ...
```

同步把 `cmd_reset.py` 补成下面这个收口：

```python
ctx.command_lock = False
ctx.command_mode = "none"
ctx._pending_lock = None
```

如果 `src/services/stage2_smoke.py` 里的 lite 上下文仍只返回 `alive/mode`, 一并补成：

```python
def build_health_snapshot(self):
    return {"alive": 1, "mode": "lite", "command_mode": "none"}
```

- [ ] **Step 4: 运行 Task 1 的测试并确认转绿**

Run: `python3 -m pytest tests/unit/test_optional_lock_commands.py -q`
Expected: PASS, 六条行为测试全部通过。

### Task 3: 用契约测试锁住协议文档口径并同步文档

**Files:**
- Create: `tests/contract/test_optional_lock_protocol_doc_contract.py`
- Modify: `.agents/skills/using-rules/references/openart-protocol.md`
- Modify: `docs/developer/control.md`

- [ ] **Step 1: 先写会失败的协议文档契约测试**

```python
"""当前底盘协议可选 lock 文档契约测试."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / ".agents" / "skills" / "using-rules" / "references" / "openart-protocol.md"
)


def test_optional_lock_protocol_doc_mentions_current_runtime_boundary() -> None:
    text = PROTOCOL_PATH.read_text(encoding="utf-8")

    required_tokens = [
        "`lock`",
        "`lock=0`",
        "`lock=1`",
        "`command_mode`",
        "`locked`",
        "`unlocked`",
        "`none`",
    ]

    for token in required_tokens:
        assert token in text, f"missing token: {token}"
```

- [ ] **Step 2: 运行契约测试并确认它先失败**

Run: `python3 -m pytest tests/contract/test_optional_lock_protocol_doc_contract.py -q`
Expected: FAIL, 原因应直接指向协议文档里还没有 `lock` / `command_mode` 当前口径。

- [ ] **Step 3: 更新正式协议文档中的控制表、查询快照和锁语义**

把 `.agents/skills/using-rules/references/openart-protocol.md` 的控制命令表与锁语义改到下面这组事实：

```md
| `vx` / `vy` | 车体系速度目标 | 控制器速度单位 | 速度 | 不接受 `lock`；作为新命令到来时会清空挂起的平面位置目标 |
| `omega` / `w` | 角速度目标 | 控制器角速度单位 | 速度 | 不接受 `lock`；作为新命令到来时会清空挂起的绝对角目标 |
| `x` / `y` / `angle` / `dx` / `dy` / `d_angle` / `rear` | 原锁定命令 | 见现有单位 | 位置 / 模式 | 默认按 `lock=1` 理解, 也可显式带 `lock=0` |
| `lock` | 原锁定命令的执行方式修饰位 | 推荐 `0/1` | 模式 | 只作用于 `x/y/angle/dx/dy/d_angle/rear` 所在整包；`1` 表示等待完成，`0` 表示无锁覆盖 |

- 原锁定命令默认按 `lock=1` 理解；显式写 `lock=0` 时，不进入 `command_lock`。
- `lock=0` 下的新命令直接覆盖当前目标，不通过“先等空闲再发下一条”的同步方式工作。
- 速度命令不接受 `lock`, 但作为新命令到来时会清空对应的旧位置目标。
- `?lock` 继续只表示当前是否处在等待完成流程。
- `?health` 新增 `command_mode`，取值固定为 `locked`、`unlocked`、`none`。
```

同时把查询示例补成：

```text
?health=alive:1,uptime_ms:1500,lock:1,rear:1,command_mode:locked,last_err:none,vision_state:ALIGN_DX
```

还要把 `docs/developer/control.md` 中“为什么要加锁”一节收口成当前实现口径：

```md
- 外部位置 / 模式命令默认继续走 `command_lock`。
- 外部命令可以显式带 `lock=0`，按无锁覆盖语义持续刷新目标。
- `?lock` 只表示是否处在等待完成流程；当前执行方式额外看 `?health.command_mode`。
```

- [ ] **Step 4: 重新运行文档契约测试并确认转绿**

Run: `python3 -m pytest tests/contract/test_optional_lock_protocol_doc_contract.py tests/contract/test_openart_protocol_doc_contract.py -q`
Expected: PASS, 新旧协议契约测试都通过。

### Task 4: 做最小回归验证并收口改动范围

**Files:**
- Verify only

- [ ] **Step 1: 运行本轮新增和受影响的自动测试**

Run: `python3 -m pytest tests/unit/test_optional_lock_commands.py tests/contract/test_optional_lock_protocol_doc_contract.py tests/contract/test_openart_protocol_doc_contract.py -q`
Expected: PASS

- [ ] **Step 2: 跑一次现有单元测试, 确认没有顺手打坏已有入口测试**

Run: `python3 -m pytest tests/unit -q`
Expected: PASS

- [ ] **Step 3: 人工核对本轮改动面只落在命令链、健康诊断和协议文档**

```text
应出现的路径：
- src/services/command_policy.py
- src/services/commands/cmd_lock.py
- src/services/transport_car.py
- src/services/stage2_smoke.py
- src/services/commands/cmd_*.py（仅本轮涉及的命令）
- tests/unit/test_optional_lock_commands.py
- tests/contract/test_optional_lock_protocol_doc_contract.py
- .agents/skills/using-rules/references/openart-protocol.md
- docs/developer/control.md
```

```text
不应顺手出现的路径：
- 视觉仓库路径
- 视觉状态机实现文件
- 运动学 / 电机 / IMU 主链大改
- 与当前 lock 语义无关的入口或目录结构改动
```

- [ ] **Step 4: 若当前会话没有真实板端联调, 结果说明里明确只完成主机侧和文档侧收口**

```text
本轮完成证据：
- 主机侧测试通过
- 当前仓库协议与开发文档已同步

仍待补的证据：
- 板端串口实测
- 上位持续发送 `lock=0` 命令时的真实动作确认
```

## 自检要点

- 计划覆盖了 Spec 中的全部硬约束：原锁定命令支持可选 `lock`、新命令抢占、`rear` 同步进入统一语义、`?health.command_mode` 可观察、当前主线仍保持位置式表达。
- 计划没有把视觉仓库、OpenArt 发包实现、视觉状态机重写或超时策略扩展混入本轮。
- 计划把最难测的路由后处理逻辑抽到纯 Python 文件里, 避免主机侧测试硬导入整车运行时。
- 计划没有包含自动提交步骤, 仍遵守“提交前先向用户确认消息”的仓库规则。
