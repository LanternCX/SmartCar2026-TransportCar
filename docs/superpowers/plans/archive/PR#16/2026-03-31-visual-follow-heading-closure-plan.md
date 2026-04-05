# 主辅车方向闭环修正收口实施计划

> **给执行代理的要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划，步骤使用复选框 `- [ ]` 跟踪。

**目标：** 让当前“主车不主动运动、视觉控辅车二维随动”主线真正建立在主辅车默认方向闭环的底盘基础能力之上，并补齐启动路径、串口分帧、设备 smoke、HIL 与内存留证口径。

**架构：** 先把主辅串口读写从“整包读完再 strip”修成稳定的逐行分帧，再把辅车执行链改成“基础速度能力默认带本地方向闭环 + 当前业务流执行二维随动”的真实输出路径，同时恢复主车与辅车同等级的底盘基础控制边界，但不把主车主动运动纳入当前业务验收。最后再把启动入口、设备 smoke、HIL 观察项、内存留证和文档口径一起收口到新的方向闭环定义上。

**技术栈：** Python 3.10、MicroPython 兼容代码、pytest、主机侧单元测试、契约测试、HIL 留证文档。

---

## 文件结构与职责

- Modify: `src/master/hw/uart.py`
  把主车串口读法改成稳定逐行分帧，避免半包、粘包直接破坏视觉与控制链路。
- Modify: `src/assistant/hw/uart.py`
  与主车一致地提供逐行分帧能力，保证辅车收包边界稳定。
- Modify: `tests/unit/master/test_app.py`
  补主车入口从“创建对象”到“可驱动主循环”的失败测试。
- Modify: `tests/unit/assistant/test_app.py`
  补辅车入口从“创建对象”到“可驱动主循环”的失败测试。
- Modify: `tests/unit/master/test_runtime_loop.py`
  补主车串口逐行消费与空拍保持行为测试。
- Modify: `tests/unit/assistant/test_runtime_loop.py`
  补辅车串口逐行消费、超时停机和状态回传测试。
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
  锁定跟随报文和最小状态回包的兼容契约。
- Modify: `src/assistant/protocol.py`
  保持当前文本协议解析边界，同时明确当前阶段接受的通用运动命令入口。
- Modify: `src/assistant/ctrl/chassis.py`
  把辅车当前执行链从“同向同占空比假动作”改成“二维平移输出 + 本地方向闭环补偿 + 超时停机”。
- Modify: `src/assistant/app.py`
  让辅车应用层驱动新的执行链，并保留最小状态回传与超时回报。
- Modify: `src/assistant/motion_runtime.py`
  继续作为辅车运行时出口，并保持与新的底盘基础能力边界一致。
- Modify: `src/assistant/runtime_params.py`
  把方向闭环相关参数从仅暴露改为真实接入。
- Modify: `tests/unit/assistant/test_motion_runtime.py`
  为方向闭环接入、二维输出方向性、超时保护和通用运动命令能力先写失败测试。
- Modify: `tests/unit/assistant/test_runtime_params.py`
  证明方向闭环参数真实影响当前输出。
- Modify: `src/master/motion_runtime.py`
  为主车补齐与辅车同等级的基础底盘控制边界，包括通用速度命令接收与方向闭环状态维护，但默认不在当前业务流中主动下发给自己。
- Modify: `src/master/app.py`
  保持“主车业务上不主动运动”，但在结构上接入基础底盘运行时能力，并让主循环入口更接近板端真实运行方式。
- Modify: `src/master/runtime_params.py`
  把主车方向闭环参数视为当前阶段必需参数，不再保留“未启用”语义。
- Modify: `tests/unit/master/test_motion_runtime.py`
  证明主车底盘基础运行时具备目标接收与方向闭环状态维护边界。
- Modify: `tests/unit/master/test_runtime_params.py`
  证明主车底盘基础运行时会读取方向闭环参数。
- Modify: `tests/unit/master/test_runtime_loop.py`
  锁定主车空拍、串口多行与控制序号行为。
- Modify: `src/master/main.py`
  让主车入口真正承担单入口启动分发职责，包括正常运行、按钮长按脚本分支与主循环装配。
- Modify: `src/assistant/main.py`
  让辅车入口真正承担单入口启动分发职责，包括正常运行、按钮长按脚本分支与主循环装配。
- Delete: `src/master/boot.py`
  删除旧入口，收口为 `main.py` 单入口。
- Delete: `src/assistant/boot.py`
  删除旧入口，收口为 `main.py` 单入口。
- Modify: `tools/run_stage2_smoke.py`
  补齐 stage2 smoke 的输出口径与失败分类记录，明确哪些项已在 smoke 验证、哪些项需转 HIL 观察。
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
  增补“随动时保持朝向稳定”的观察项与失败分类。
- Create: `tests/unit/tools/test_run_stage2_smoke.py`
  锁定 smoke 输出口径，明确它验证的是部署、导入、最小探针与观察项登记，不替代 HIL 动作现象。
- Create: `docs/superpowers/memory/debug/entries/2026-03/2026-03-31-1.md`
  记录本轮实现阶段内存留证，包括 owner、阶段、分类和影响判断。

## 实施任务

### TDD 固定收口要求

- [ ] 每个任务在 `RED -> GREEN` 后都必须补一次最小 `REFACTOR`
- [ ] `REFACTOR` 只允许做命名整理、重复消除、边界收紧和注释澄清，不允许新增行为
- [ ] `REFACTOR` 后必须重跑该任务对应测试，确认仍然全绿

### Task 1: 修正主辅串口逐行分帧

**Files:**
- Modify: `src/master/hw/uart.py`
- Modify: `src/assistant/hw/uart.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`

- [ ] **Step 1: 先写失败测试，锁定串口不会把半包和粘包直接当成一整行返回**

```python
def test_uart_port_read_line_buffers_partial_and_returns_one_line_at_a_time() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self):
            self.chunks = [b"follow=1,seq=1", b",valid=1,dx=1.0,dy=0.0\r\nPING\r\n"]

        def any(self):
            return len(self.chunks[0]) if self.chunks else 0

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    port._device = FakeDevice()

    assert port.read_line() is None
    assert port.read_line() == "follow=1,seq=1,valid=1,dx=1.0,dy=0.0"
    assert port.read_line() == "PING"
```

- [ ] **Step 2: 运行相关测试，确认当前实现确实因为整包读取而失败**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: FAIL，暴露 `read_line()` 不能正确处理半包或粘包。

- [ ] **Step 3: 最小实现逐行缓冲读取**

```python
class UartPort:
    def __init__(self, ...):
        self._read_buffer = ""

    def read_line(self):
        payload = self.read()
        if payload is not None:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            self._read_buffer += str(payload)
        if "\n" not in self._read_buffer:
            return None
        line, self._read_buffer = self._read_buffer.split("\n", 1)
        return line.strip("\r")
```

- [ ] **Step 4: 重跑测试，确认主辅串口分帧行为稳定**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: PASS。

### Task 2: 让辅车执行链真实经过方向闭环补偿

**Files:**
- Modify: `src/assistant/protocol.py`
- Modify: `src/assistant/ctrl/chassis.py`
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/runtime_params.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_runtime_params.py`

- [ ] **Step 1: 先写失败测试，锁定辅车所有基础运动能力默认都经过方向闭环**

```python
def test_motion_runtime_applies_heading_hold_while_following_dx_dy() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    class FakeMotor:
        def __init__(self):
            self.duty_history = []

        def set_duty(self, duty):
            self.duty_history.append(duty)

        def stop(self):
            self.duty_history.append(0)

    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}
    imu = {"heading_deg": lambda: 12.0}
    runtime = MotionRuntime(timeout_ms=100, hw_bundle={"motors": motors, "imu": imu})

    runtime.apply_command(
        parse_command("follow=1,seq=1,valid=1,dx=0.20,dy=0.10"),
        now_ms=0,
    )

    duties = [motors[name].duty_history[-1] for name in ("m", "l", "r")]
    assert len(set(duties)) > 1
    assert runtime.state.velocity_command[2] != 0.0
```

```python
def test_motion_runtime_maps_dx_and_dy_signs_to_expected_motion_direction() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    runtime.apply_command(parse_command("follow=1,seq=1,valid=1,dx=0.20,dy=0.00"), now_ms=0)
    right_output = runtime.state.velocity_command
    runtime.apply_command(parse_command("follow=1,seq=2,valid=1,dx=-0.20,dy=0.00"), now_ms=1)
    left_output = runtime.state.velocity_command
    runtime.apply_command(parse_command("follow=1,seq=3,valid=1,dx=0.00,dy=0.20"), now_ms=2)
    forward_output = runtime.state.velocity_command
    runtime.apply_command(parse_command("follow=1,seq=4,valid=1,dx=0.00,dy=-0.20"), now_ms=3)
    backward_output = runtime.state.velocity_command

    assert right_output[0] > 0.0
    assert left_output[0] < 0.0
    assert forward_output[1] > 0.0
    assert backward_output[1] < 0.0
```

```python
def test_motion_runtime_accepts_vel_command_as_base_chassis_capability() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    result = runtime.apply_command(parse_command("VEL 0.1 0.0 0.2"), now_ms=0)

    assert result == "BUSY"
    assert runtime.state.velocity_command == (0.1, 0.0, 0.2)
```

```python
def test_motion_runtime_keeps_heading_hold_for_vel_command_by_default() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100, hw_bundle={"imu": {"heading_deg": lambda: 15.0}})

    runtime.apply_command(parse_command("VEL 0.1 0.0 0.0"), now_ms=0)

    assert runtime.state.velocity_command[2] != 0.0
```

```python
def test_assistant_runtime_reads_yaw_params_into_current_output() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    old_kp = runtime_params.YAW_KP
    runtime_params.YAW_KP = 0.5
    try:
        runtime = MotionRuntime(timeout_ms=100)
        runtime.apply_command(
            parse_command("follow=1,seq=1,valid=1,dx=0.1,dy=0.0"),
            now_ms=0,
        )
    finally:
        runtime_params.YAW_KP = old_kp

    assert runtime.state.velocity_command[2] != 0.0
```

- [ ] **Step 2: 运行辅车运行时测试，确认当前实现仍然是假闭环且基础速度能力绕开方向闭环**

Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_runtime_params.py -q`
Expected: FAIL，暴露 `VEL` 被拒绝或绕开方向闭环、三路输出无方向差异、偏航参数未真实影响当前输出。

- [ ] **Step 3: 最小实现本地方向闭环补偿与通用速度命令入口**

```python
def _compute_heading_correction(self):
    heading = self._read_heading_deg()
    error = self.target_heading_deg - heading
    self._yaw_integral = clamp(self._yaw_integral + error, -self.yaw_i_max, self.yaw_i_max)
    omega = error * self.yaw_kp + self._yaw_integral * self.yaw_ki
    return clamp(omega, -self.auto_omega_max, self.auto_omega_max)

def _apply_follow(self, command, now_ms):
    ...
    omega = self._compute_heading_correction()
    self.state.velocity_command = (limited_dx, limited_dy, omega)
    self._apply_motor_output(limited_dx, limited_dy, omega)
    return "BUSY"

def apply_command(self, command, now_ms):
    if command.kind == "vel":
        return self._apply_velocity(command, now_ms)
```

- [ ] **Step 4: 重跑辅车相关测试，确认方向闭环已经进入当前主线**

Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_runtime_params.py tests/unit/assistant/test_runtime_loop.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_runtime_params.py tests/unit/assistant/test_runtime_loop.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

### Task 3: 补齐主车同等级底盘基础能力但保持业务上不主动运动

**Files:**
- Modify: `src/master/motion_runtime.py`
- Modify: `src/master/app.py`
- Modify: `src/master/runtime_params.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_motion_runtime.py`
- Modify: `tests/unit/master/test_runtime_params.py`

- [ ] **Step 1: 先写失败测试，锁定主车也默认维持方向闭环状态，并具备同等级基础底盘能力**

```python
def test_master_motion_runtime_accepts_base_velocity_command() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    target = runtime.apply_self_target({"kind": "vel", "vx": 0.1, "vy": 0.0, "omega": 0.2})

    assert target == {"kind": "vel", "vx": 0.1, "vy": 0.0, "omega": 0.2}
    assert runtime.last_target == target
```

```python
def test_master_motion_runtime_reads_yaw_runtime_params() -> None:
    import master.runtime_params as runtime_params
    from master.motion_runtime import MotionRuntime

    old_kp = runtime_params.YAW_KP
    runtime_params.YAW_KP = 0.42
    try:
        runtime = MotionRuntime()
    finally:
        runtime_params.YAW_KP = old_kp

    assert runtime.yaw_kp == 0.42
```

```python
def test_master_motion_runtime_keeps_heading_hold_state_by_default() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert runtime.heading_hold_enabled is True
```

```python
def test_master_motion_runtime_heading_hold_output_changes_with_heading_error() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.apply_self_target({"kind": "vel", "vx": 0.1, "vy": 0.0, "omega": 0.0})

    output = runtime.update_heading_hold(current_heading_deg=15.0)

    assert output["omega"] != 0.0
```

```python
def test_master_app_current_stage_still_holds_self_motion_in_visual_follow_flow() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
        }
    )

    assert result["self_target"] == {"kind": "hold"}
    assert result["assistant_command"].startswith("follow=1,")
```

- [ ] **Step 2: 运行主车相关测试，确认当前实现只有业务保持，没有基础底盘能力表达**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py tests/unit/master/test_runtime_params.py -q`
Expected: FAIL，暴露主车运行时没有读入方向闭环参数、没有默认方向闭环状态，或没有可验证的基础速度能力输出边界。

- [ ] **Step 3: 最小补齐主车基础底盘运行时参数与状态边界**

```python
class MotionRuntime:
    def __init__(self):
        self.last_target = {"kind": "hold"}
        self.heading_hold_enabled = True
        self.yaw_kp = float(runtime_params.YAW_KP)
        self.yaw_ki = float(runtime_params.YAW_KI)
        self.yaw_i_max = float(runtime_params.YAW_I_MAX)
        self.auto_omega_max = float(runtime_params.AUTO_OMEGA_MAX)

    def update_heading_hold(self, current_heading_deg):
        ...
```

- [ ] **Step 4: 重跑主车测试，确认“业务不主动运动”与“底盘具备基础能力”同时成立**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py tests/unit/master/test_runtime_params.py tests/unit/master/test_runtime_loop.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py tests/unit/master/test_runtime_params.py tests/unit/master/test_runtime_loop.py -q`
Expected: PASS。

### Task 4: 修正启动入口与主循环表达

**Files:**
- Modify: `src/master/main.py`
- Modify: `src/assistant/main.py`
- Delete: `src/master/boot.py`
- Delete: `src/assistant/boot.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`

- [ ] **Step 1: 先写失败测试，锁定 `main.py` 是唯一公开入口，并负责按钮长按分发和正常运行装配**

```python
def test_master_main_dispatches_runtime_when_no_button_is_held() -> None:
    from master.main import main

    runtime = main(button_reader=lambda pin: False)

    assert callable(runtime.step)
```

```python
def test_master_main_dispatches_pid_identify_when_c8_is_held() -> None:
    from master.main import main

    result = main(button_reader=lambda pin: pin == "C8")

    assert result == "pid_identify"
```

```python
def test_assistant_main_dispatches_calibrate_gyro_when_c9_is_held() -> None:
    from assistant.main import main

    result = main(button_reader=lambda pin: pin == "C9")

    assert result == "calibrate_gyro"
```

```python
def test_runtime_entry_layout_only_keeps_main_py_as_public_entry() -> None:
    from pathlib import Path

    assert (Path("src/master/main.py")).exists()
    assert (Path("src/assistant/main.py")).exists()
    assert not (Path("src/master/boot.py")).exists()
    assert not (Path("src/assistant/boot.py")).exists()
```

- [ ] **Step 2: 运行入口测试，确认当前实现还没有真正收口到 `main.py` 单入口分发**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/test_runtime_entry_layout.py -q`
Expected: FAIL，暴露 `main.py` 还没有按钮长按分发能力，或仓库仍保留 `boot.py` 双入口口径。

- [ ] **Step 3: 最小修正主辅入口与旧入口清理方式**

```python
def main(button_reader=None):
    if _is_button_held("C8", button_reader):
        return "pid_identify"
    if _is_button_held("C9", button_reader):
        return "calibrate_gyro"
    return build_runtime_loop()
```

要求：入口说明必须明确这是唯一公开入口；删除 `boot.py`；并保持 `src/master` 与 `src/assistant` 作为根目录时可直接导入。

- [ ] **Step 4: 重跑入口测试，确认主辅入口表达清晰且兼容当前根目录直烧场景**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/test_runtime_entry_layout.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/test_runtime_entry_layout.py -q`
Expected: PASS。

### Task 5: 收口契约、设备 smoke、HIL 与内存留证

**Files:**
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
- Modify: `tools/run_stage2_smoke.py`
- Create: `tests/unit/tools/test_run_stage2_smoke.py`
- Create: `docs/superpowers/memory/debug/entries/2026-03/2026-03-31-1.md`

- [ ] **Step 1: 先写失败测试和文档差异，锁定最小契约与 HIL 观察项**

```python
def test_assistant_vel_command_contract() -> None:
    from assistant.protocol import parse_command

    parsed = parse_command("VEL 0.1 0.0 0.2")

    assert parsed.kind == "vel"
    assert parsed.vx == 0.1
    assert parsed.omega == 0.2
```

HIL 文档必须新增：

- 收到有效跟随后是否进入随动状态
- 朝正确平移方向随动
- 随动时保持当前朝向稳定
- 若持续自旋则记为失败
- 若随动过程中持续偏航漂移到新的稳定朝向则记为失败
- 若超时后停机但仍持续偏航，则记为失败

- [ ] **Step 2: 运行契约测试，确认当前阶段契约尚未覆盖新的基础能力**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小补齐契约与 HIL 留证文本**

- [ ] **Step 4: 先为 stage2 smoke 缺口补失败用例或缺口记录，并把方向稳定观察项写入 smoke 输出口径**

```python
def test_stage2_smoke_reports_follow_stage_checkpoints() -> None:
    from tools.run_stage2_smoke import build_smoke_summary

    summary = build_smoke_summary(port="/dev/mock", query_ok=True, smoke_ok=True)

    assert "已登记检查: 进入随动状态" in summary
    assert "已登记检查: 朝向稳定需转 HIL 确认" in summary
    assert "已登记检查: 超时后停止且不持续自旋需转 HIL 确认" in summary
```

Run: `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: FAIL，暴露当前 smoke 还没有覆盖方向闭环相关输出口径。

- [ ] **Step 5: 对主车执行最小板端 smoke 并记录结果**

Run: `python3 tools/run_stage2_smoke.py --port <master-port>`
Expected: 输出统一失败分类之一：`connect_failed`、`deploy_failed`、`probe_failed`、`observe_failed`、`hil_pending`；并在 `tests/hil/2026-03-30-visual-center-follow.md` 记录主车端口、命令顺序、结果与原因。

- [ ] **Step 6: 对辅车执行最小板端 smoke 并记录结果**

Run: `python3 tools/run_stage2_smoke.py --port <assistant-port>`
Expected: 输出统一失败分类之一：`connect_failed`、`deploy_failed`、`probe_failed`、`observe_failed`、`hil_pending`；并在 `tests/hil/2026-03-30-visual-center-follow.md` 记录辅车端口、命令顺序、结果与原因。

- [ ] **Step 7: 运行当前主线最小回归**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **Step 8: 无条件补 `tests/hil/2026-03-30-visual-center-follow.md` 观察记录模板**

要求：明确记录“进入随动状态”“朝正确平移方向随动”“随动 + 朝向稳定”是否同时成立，并沿用统一失败分类。

- [ ] **Step 9: 补实现阶段内存留证**

产物路径：`docs/superpowers/memory/debug/entries/2026-03/2026-03-31-1.md`

要求：按实现规则记录本轮新增常驻对象、唯一 owner、加载阶段、分类，以及对 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle`、`diag_survival` 的影响判断；若没有新增常驻对象，也要明确写出“不新增”的证据和对应理由。

- [ ] **Step 10: 更新本轮 review 门禁清单并逐项自检**

要求：把以下 5 个顺序门禁写入 `tests/hil/2026-03-30-visual-center-follow.md` 或本轮收口记录，并逐项填写结果：

1. 主辅车能否直接作为独立根目录烧录运行
2. 整条主线链路是否真正闭合
3. 当前主线参数是否完整归位
4. 内存留证是否支持当前结论
5. 主辅车底盘是否默认维持自身方向闭环，且辅车随动时是否始终维持该闭环
