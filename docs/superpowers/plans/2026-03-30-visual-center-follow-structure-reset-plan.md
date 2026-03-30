# 主辅车最小闭环结构纠偏 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前阶段“辅车色标二维回中”迁移到新的 `hw/`、`ctrl/`、`vision/`、`script/` 框架中，同时补齐主辅车的电机、编码器、IMU、UART 板级薄封装与运行时装配入口。

**Architecture:** 先用测试锁定新的目录边界与装配入口，再先补齐 `hw/` 层和运行时接入口，最后把主车视觉链和辅车跟随执行链迁入新目录。板级层只写仓库正文已经确认的硬件事实，不做注册表、工厂表或字符串查找；一旦遇到仓库正文未确认或彼此冲突的引脚事实，立即停下向用户确认，不猜测。视觉、协议、状态机、决策保持硬件无关并继续在主机侧测试。

**Tech Stack:** Python 3.8+、MicroPython 兼容代码、pytest、主机侧单元测试、契约测试、HIL 留证文档。

---

## 文件结构与职责

- Create: `src/master/config.py`
  主车当前阶段配置常量与已确认硬件映射。
- Create: `src/master/hw/uart.py`
  主车 `UART3/UART6/UART8` 板级薄封装与最小读写接口。
- Create: `src/master/hw/motors.py`
  主车三路电机对象创建、占空比输出与安全停机入口。
- Create: `src/master/hw/encoders.py`
  主车三路编码器对象创建、原始计数读取与清零入口。
- Create: `src/master/hw/imu.py`
  主车 IMU 初始化、原始数据读取与零漂入口。
- Create: `src/master/vision/parser.py`
  主车视觉文本解析。
- Create: `src/master/vision/ingress.py`
  双路视觉缓存、选路、新鲜度与误差语义统一。
- Create: `src/master/vision/state_machine.py`
  `MARKER_MISSING / TRACKING / CENTER_HOLD` 低频状态机。
- Create: `src/master/vision/decision.py`
  当前阶段二维 `dx/dy` 控制语义生成。
- Create: `src/master/ctrl/filters.py`
- Create: `src/master/ctrl/pid.py`
- Create: `src/master/ctrl/kinematics.py`
- Create: `src/master/ctrl/attitude.py`
- Create: `src/master/ctrl/chassis.py`
- Create: `src/master/ctrl/ident.py`
- Create: `src/master/ctrl/storage.py`
  主车控制骨架、运行时边界与脚本/存储接入口。
- Create: `src/master/script/pid_identify.py`
- Create: `src/master/script/calibrate_gyro.py`
  主车脚本入口占位，先接到新的 `ctrl/` / `hw/` 边界。
- Modify: `src/master/app.py`
  改为主车装配层，只连接 `hw/`、`vision/`、`ctrl/` 与协议。
- Modify: `src/master/main.py`
  改为新的主车唯一入口。
- Modify: `src/master/protocol.py`
  保留主车到辅车的最小文本协议构造。
- Modify: `src/master/decision.py`
- Modify: `src/master/vision_ingress.py`
- Modify: `src/master/vision_state_machine.py`
- Modify: `src/master/motion_runtime.py`
  收口或移除旧平铺实现，避免继续在旧结构上承载主线逻辑。
- Create: `src/assistant/config.py`
  辅车当前阶段配置常量与已确认硬件映射。
- Create: `src/assistant/hw/uart.py`
  辅车 `UART3` 板级薄封装与最小读写接口。
- Create: `src/assistant/hw/motors.py`
- Create: `src/assistant/hw/encoders.py`
- Create: `src/assistant/hw/imu.py`
  辅车底盘相关板级薄封装。
- Create: `src/assistant/ctrl/filters.py`
- Create: `src/assistant/ctrl/pid.py`
- Create: `src/assistant/ctrl/kinematics.py`
- Create: `src/assistant/ctrl/attitude.py`
- Create: `src/assistant/ctrl/chassis.py`
- Create: `src/assistant/ctrl/ident.py`
- Create: `src/assistant/ctrl/storage.py`
  辅车控制骨架与当前阶段随动运行时。
- Create: `src/assistant/script/pid_identify.py`
- Create: `src/assistant/script/calibrate_gyro.py`
  辅车脚本入口占位。
- Modify: `src/assistant/app.py`
  改为辅车装配层，只连接协议、底盘运行时与最小回包语义。
- Modify: `src/assistant/main.py`
  改为新的辅车唯一入口。
- Modify: `src/assistant/protocol.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/status.py`
- Modify: `src/assistant/safety.py`
  收口或移除旧平铺实现，避免继续在旧结构上承载主线逻辑。
- Create: `tests/unit/master/test_structure_runtime.py`
  锁定主车新目录、装配入口与兼容转发行为。
- Create: `tests/unit/assistant/test_structure_runtime.py`
  锁定辅车新目录、装配入口与兼容转发行为。
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_decision.py`
- Modify: `tests/unit/master/test_vision_ingress.py`
- Modify: `tests/unit/master/test_vision_state_machine.py`
- Modify: `tests/unit/master/test_motion_runtime.py`
  改为从新目录验证主车当前阶段行为与新装配边界。
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_protocol.py`
- Modify: `tests/unit/assistant/test_status.py`
  改为从新目录验证辅车当前阶段行为与新装配边界。
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
  锁定主辅协议在新框架下的一致性。
- Modify: `tests/unit/test_runtime_entry_layout.py`
  增加对 `hw/`、`ctrl/`、`vision/`、`script/` 新边界存在性的检查。
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
  补充新框架下的 HIL 留证步骤。

## 实施任务

### Task 1: 锁定新框架边界与兼容入口

**Files:**
- Create: `tests/unit/master/test_structure_runtime.py`
- Create: `tests/unit/assistant/test_structure_runtime.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`

- [ ] **Step 1: 先写失败测试，固定主辅车新目录边界与入口兼容要求**

```python
def test_master_runtime_exposes_new_structure_packages() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src" / "master"
    for name in ("hw", "ctrl", "vision", "script"):
        assert (root / name).is_dir()
```

```python
def test_assistant_runtime_exposes_new_structure_packages() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src" / "assistant"
    for name in ("hw", "ctrl", "script"):
        assert (root / name).is_dir()
```

- [ ] **Step 2: 运行结构测试，确认当前实现确实失败**

Run: `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: FAIL，提示缺少 `hw/`、`ctrl/`、`vision/`、`script/` 目录与对应入口。

- [ ] **Step 3: 最小创建目录与包入口，为后续迁移铺路**

```python
# src/master/hw/__init__.py
# src/master/ctrl/__init__.py
# src/master/vision/__init__.py
# src/master/script/__init__.py
```

- [ ] **Step 4: 重跑结构测试，确认边界落地**

Run: `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。

### Task 2: 先补齐主辅车硬件层薄封装

**Files:**
- Create: `src/master/config.py`
- Create: `src/master/hw/uart.py`
- Create: `src/master/hw/motors.py`
- Create: `src/master/hw/encoders.py`
- Create: `src/master/hw/imu.py`
- Create: `src/assistant/config.py`
- Create: `src/assistant/hw/uart.py`
- Create: `src/assistant/hw/motors.py`
- Create: `src/assistant/hw/encoders.py`
- Create: `src/assistant/hw/imu.py`
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **Step 1: 先写失败测试，固定四类硬件层真实存在并且有运行时装配入口**

```python
def test_master_hw_modules_are_importable() -> None:
    from master.app import build_hw_bundle
    from master.hw import uart, motors, encoders, imu

    assert uart is not None
    assert motors is not None
    assert encoders is not None
    assert imu is not None
    assert build_hw_bundle is not None
```

```python
def test_assistant_hw_modules_are_importable() -> None:
    from assistant.app import build_hw_bundle
    from assistant.hw import uart, motors, encoders, imu

    assert uart is not None
    assert motors is not None
    assert encoders is not None
    assert imu is not None
    assert build_hw_bundle is not None
```

- [ ] **Step 2: 运行结构测试，确认当前缺少真实硬件层**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小实现主辅车板级薄封装，并先只写仓库正文已确认的硬件事实**

```python
MASTER_UART_IDS = {"uart3": 2, "uart6": 5, "uart8": 7}
MASTER_UART_BAUDRATE = 115200
```

```python
def build_hw_bundle():
    return {
        "uart": build_uart_bundle(),
        "motors": build_motor_bundle(),
        "encoders": build_encoder_bundle(),
        "imu": build_imu_bundle(),
    }
```

若进入电机或编码器真实引脚实现时发现仓库正文仍未统一确认，则本任务在该子步暂停并等待用户确认。

- [ ] **Step 4: 重跑结构测试，确认硬件层与装配入口已真实补齐**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。

### Task 3: 迁移主车视觉链到 `vision/`

**Files:**
- Create: `src/master/vision/parser.py`
- Create: `src/master/vision/ingress.py`
- Create: `src/master/vision/state_machine.py`
- Create: `src/master/vision/decision.py`
- Modify: `src/master/app.py`
- Modify: `src/master/decision.py`
- Modify: `src/master/vision_ingress.py`
- Modify: `src/master/vision_state_machine.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_decision.py`
- Modify: `tests/unit/master/test_vision_ingress.py`
- Modify: `tests/unit/master/test_vision_state_machine.py`

- [ ] **Step 1: 先写失败测试，要求主车行为通过新目录入口暴露**

```python
def test_master_app_uses_new_vision_pipeline() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation({"control_seq": 1, "valid": 0})

    assert decision.assistant_command == "follow=1,seq=1,valid=0,dx=0.000,dy=0.000"
```

- [ ] **Step 2: 运行主车相关测试，确认迁移前失败**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/master/test_decision.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小迁移视觉解析、双路缓存、状态机与二维决策到 `vision/`，并从 `app.py` 直接装配新模块**

```python
from master.vision.decision import decide_from_observation

decision = decide_from_observation(observation)
```

- [ ] **Step 4: 重跑主车测试，确认新框架下主线行为未变**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/master/test_decision.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py -q`
Expected: PASS。

### Task 4: 补齐主车 `ctrl/` 与脚本边界

**Files:**
- Create: `src/master/ctrl/filters.py`
- Create: `src/master/ctrl/pid.py`
- Create: `src/master/ctrl/kinematics.py`
- Create: `src/master/ctrl/attitude.py`
- Create: `src/master/ctrl/chassis.py`
- Create: `src/master/ctrl/ident.py`
- Create: `src/master/ctrl/storage.py`
- Create: `src/master/script/pid_identify.py`
- Create: `src/master/script/calibrate_gyro.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `tests/unit/master/test_motion_runtime.py`
- Modify: `tests/unit/master/test_structure_runtime.py`

- [ ] **Step 1: 先写失败测试，固定主车控制骨架与脚本接入口**

```python
def test_master_ctrl_chassis_exposes_core_runtime_boundary() -> None:
    from master.ctrl.chassis import CoreRuntime, ChassisRuntime

    assert CoreRuntime is not None
    assert ChassisRuntime is not None
```

- [ ] **Step 2: 运行主车骨架测试，确认当前缺少这些边界**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_structure_runtime.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小实现主车控制骨架与脚本入口，并把运行时 owner 收口到新边界**

```python
class CoreRuntime:
    def __init__(self, hw_bundle):
        self.hw = hw_bundle
```

```python
class ChassisRuntime:
    def __init__(self, core_runtime):
        self.core = core_runtime
```

- [ ] **Step 4: 重跑主车骨架测试**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_structure_runtime.py -q`
Expected: PASS。

### Task 5: 迁移辅车执行链到 `ctrl/`

**Files:**
- Create: `src/assistant/ctrl/filters.py`
- Create: `src/assistant/ctrl/pid.py`
- Create: `src/assistant/ctrl/kinematics.py`
- Create: `src/assistant/ctrl/attitude.py`
- Create: `src/assistant/ctrl/chassis.py`
- Create: `src/assistant/ctrl/ident.py`
- Create: `src/assistant/ctrl/storage.py`
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/status.py`
- Modify: `src/assistant/safety.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_status.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **Step 1: 先写失败测试，要求辅车跟随运行时通过 `assistant.ctrl.chassis` 暴露**

```python
def test_assistant_ctrl_chassis_handles_follow_runtime() -> None:
    from assistant.ctrl.chassis import ChassisRuntime

    runtime = ChassisRuntime(timeout_ms=100)
    assert runtime is not None
```

- [ ] **Step 2: 运行辅车相关测试，确认迁移前失败**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_status.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小迁移辅车随动执行、安全停机和状态回包到 `ctrl/`，并从 `app.py` 直接装配新运行时**

```python
class ChassisRuntime:
    def apply_command(self, command, now_ms):
        return self.runtime.apply_command(command, now_ms)
```

- [ ] **Step 4: 重跑辅车测试，确认新框架下行为未变**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_status.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。

### Task 6: 收口入口、契约与 HIL 留证

**Files:**
- Modify: `src/master/main.py`
- Modify: `src/assistant/main.py`
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`

- [ ] **Step 1: 先写失败测试，固定主辅协议在新框架下保持一致**

```python
def test_master_assistant_motion_protocol_contract() -> None:
    from master.protocol import build_follow_command
    from assistant.protocol import parse_command

    parsed = parse_command(build_follow_command(seq=3, valid=1, dx=0.1, dy=0.0))
    assert parsed.kind == "follow"
```

- [ ] **Step 2: 运行契约与入口测试，确认迁移后仍需收口**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py tests/unit/test_runtime_entry_layout.py -q`
Expected: 若入口或契约仍未完全对齐则 FAIL。

- [ ] **Step 3: 最小调整 `main.py`、契约测试与 HIL 文档，收口到新框架**

```python
def main():
    return MasterApp()
```

- [ ] **Step 4: 运行目标验证集，确认结构、行为与契约都通过**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **Step 5: 更新 HIL 留证文档，记录当前仍需板端验证的步骤**

```text
- 验证主车 UART6/UART8 持续接收
- 验证辅车 UART3 跟随接收
- 验证无目标和超时时输出归零
```

### Task 7: 补齐辅车 `script/` 边界

**Files:**
- Create: `src/assistant/script/pid_identify.py`
- Create: `src/assistant/script/calibrate_gyro.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **Step 1: 先写失败测试，固定辅车脚本目录与入口真实存在**

```python
def test_assistant_script_entries_exist() -> None:
    from assistant.script import pid_identify, calibrate_gyro

    assert pid_identify is not None
    assert calibrate_gyro is not None
```

- [ ] **Step 2: 运行结构测试，确认当前缺少辅车脚本入口**

Run: `python3 -m pytest tests/unit/assistant/test_structure_runtime.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小创建辅车脚本入口，并只接到新 `ctrl/` / `hw/` 边界，不补功能细节**

```python
def main():
    return "script_pending"
```

- [ ] **Step 4: 重跑结构测试，确认辅车 `script/` 边界已落地**

Run: `python3 -m pytest tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。
