# 主辅包完整底座航向角闭环实施计划

> **给执行代理的要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划，步骤使用复选框 `- [ ]` 跟踪。

**Goal:** 让 `src/master` 与 `src/assistant` 成为可直接烧录到 RT1021 根目录的完整运行包，并接回 `IMU + 编码器 + 里程 + 航向角闭环` 底座主数据链，在此基础上完成主车视觉输入与辅车随动联合闭环。

**Architecture:** 先停止围绕主机侧测试组织实现，优先把板端真实主链接通：根目录直烧路径、主辅完整硬件装配、IMU/编码器/里程/航向角闭环、联合控制链挂接。待真实板端主链实现完成后，再对纯逻辑边界补主机侧 TDD 保护，最后做板端三层验证留证。

**Tech Stack:** Python 3.10、MicroPython 兼容代码、RT1021、pytest、mpy-cli、HIL 留证文档、legacy 底座主数据链参考实现。

---

## 文件结构与职责

- Modify: `src/master/main.py`
  改成真正适合 RT1021 根目录直烧的主车入口，不再依赖包外层目录形态。
- Modify: `src/assistant/main.py`
  改成真正适合 RT1021 根目录直烧的辅车入口，不再依赖包外层目录形态。
- Modify: `src/master/app.py`
  让主车运行时 owner 持有完整硬件装配，并把底座主链与视觉/串口控制重新挂接。
- Modify: `src/assistant/app.py`
  让辅车运行时 owner 持有完整硬件装配，并把底座主链与串口执行/状态回包重新挂接。
- Modify: `src/master/motion_runtime.py`
  参考 legacy 接回主车底座主数据链：IMU、编码器、里程、航向角闭环。
- Modify: `src/assistant/motion_runtime.py`
  参考 legacy 接回辅车底座主数据链：IMU、编码器、里程、航向角闭环。
- Modify: `src/master/hw/imu.py`
  提供主车 IMU 真实读数、零偏接入、姿态估计所需最小接口。
- Modify: `src/assistant/hw/imu.py`
  提供辅车 IMU 真实读数、零偏接入、姿态估计所需最小接口。
- Modify: `src/master/hw/encoders.py`
  提供主车编码器真实读数与清零接口，满足轮速与里程计算。
- Modify: `src/assistant/hw/encoders.py`
  提供辅车编码器真实读数与清零接口，满足轮速与里程计算。
- Modify: `src/master/vision/decision.py`
  把主车视觉输入重新挂到完整底座主链，不再只输出“壳级控制目标”。
- Modify: `src/master/vision/ingress.py`
  维持视觉输入边界，并为主车底座/控制层提供稳定输入。
- Modify: `src/master/vision/state_machine.py`
  保留状态机边界，但只处理阶段切换，不承载底座闭环算法。
- Modify: `src/assistant/ctrl/chassis.py`
  把辅车控制输入真正挂到完整底座闭环运行时，而不是只停留在半套执行壳。
- Modify: `src/master/runtime_params.py`
  接回主车底座闭环所需 legacy 参数。
- Modify: `src/assistant/runtime_params.py`
  接回辅车底座闭环所需 legacy 参数。
- Modify: `src/master/protocol.py`
  必要时扩主车对辅车的控制字段与状态解析边界。
- Modify: `src/assistant/protocol.py`
  必要时扩辅车控制字段与状态回包边界。
- Modify: `tests/unit/master/test_app.py`
  只保留适合 TDD 的主车入口、装配、纯逻辑边界测试。
- Modify: `tests/unit/assistant/test_app.py`
  只保留适合 TDD 的辅车入口、装配、纯逻辑边界测试。
- Modify: `tests/unit/master/test_motion_runtime.py`
  补主车底座主数据链中的纯算法测试。
- Modify: `tests/unit/assistant/test_motion_runtime.py`
  补辅车底座主数据链中的纯算法测试。
- Modify: `tests/unit/master/test_runtime_loop.py`
  补主车持续视觉输入与持续控制输出的纯逻辑保护。
- Modify: `tests/unit/assistant/test_runtime_loop.py`
  补辅车持续控制执行与状态输出的纯逻辑保护。
- Modify: `tests/unit/assistant/test_hw_motors.py`
  仅保留适合主机侧保护的电机边界语义测试。
- Modify: `tools/run_stage2_smoke.py`
  为主车独立、辅车独立、联合链路三层板端验证服务。
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
  重写为三层板端验证记录入口。

## 执行原则

- [ ] **原则 1：先实现真实板端主链，不先追求主机侧测试绿色**
- [ ] **原则 2：不以主机侧测试替代板端完整闭环验收**
- [ ] **原则 3：只有纯逻辑、确定性边界才进入 TDD**
- [ ] **原则 4：每完成一层板端主链后，再补对应纯逻辑测试保护**

## Task 1: 收口主辅根目录直烧入口形态（先实现，不以 TDD 判完成）

**Files:**
- Modify: `src/master/main.py`
- Modify: `src/assistant/main.py`
- Modify: `src/master/app.py`
- Modify: `src/assistant/app.py`

- [ ] **Step 1: 先读当前入口与装配路径，列出所有仍依赖包外层目录的点**

- [ ] **Step 2: 直接修改入口与装配，让 `src/master` / `src/assistant` 以 RT1021 根目录形态存在**

```python
# 目标示意：板端根目录直接存在这些文件，不再假设外层包名
from app import MasterRuntimeLoop, build_hw_bundle
from script.calibrate_gyro import main as run_calibrate_gyro
from script.pid_identify import main as run_pid_identify
```

- [ ] **Step 3: 确认 `main.py` 正常分支仍直接进入持续主循环，不被中途回退逻辑打断**

- [ ] **Step 4: 只做最小主机侧烟雾验证，不把这一层误判为“完整完成”**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: 入口与装配相关纯逻辑测试保持通过。

## Task 2: 接回主辅底座主数据链（先实现，不以 TDD 判完成）

**Files:**
- Modify: `src/master/hw/imu.py`
- Modify: `src/assistant/hw/imu.py`
- Modify: `src/master/hw/encoders.py`
- Modify: `src/assistant/hw/encoders.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/master/runtime_params.py`
- Modify: `src/assistant/runtime_params.py`

- [ ] **Step 1: 对照 legacy，确认主链最低必要对象与调用顺序**

参考：
- `src/legacy/services/runtime/motion_runtime.py`
- `src/legacy/config/params.py`
- `src/legacy/storage/param_manager.py`

- [ ] **Step 2: 直接实现 IMU 真读数与零偏接入，不先写主机侧模拟闭环测试**

- [ ] **Step 3: 直接实现编码器真读数与清零接入，不先写主机侧模拟闭环测试**

- [ ] **Step 4: 直接把里程与航向角闭环主链接回主辅两边的 `motion_runtime.py`**

```python
# 目标语义示意：先把真实主链接通
imu_raw = imu.read_raw()
encoder_ticks = {name: port.read() for name, port in encoders.items()}
heading_est = estimator.update(imu_raw, offsets)
odom_x, odom_y = odometry.update(encoder_ticks, heading_est)
omega_cmd = yaw_controller.update(target_heading, heading_est)
```

- [ ] **Step 5: 确认主辅运行时 owner 真正持有完整装配，并且默认进入自身航向角保持**

## Task 3: 把主车视觉输入与辅车随动挂回完整底座主链（先实现，不以 TDD 判完成）

**Files:**
- Modify: `src/master/app.py`
- Modify: `src/master/vision/decision.py`
- Modify: `src/master/vision/ingress.py`
- Modify: `src/master/vision/state_machine.py`
- Modify: `src/master/protocol.py`
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/ctrl/chassis.py`
- Modify: `src/assistant/protocol.py`

- [ ] **Step 1: 先把主车视觉输出重新挂到完整底座运行时，而不是当前壳级 `self_target`**

- [ ] **Step 2: 先把辅车控制执行重新挂到完整底座运行时，而不是当前半套执行壳**

- [ ] **Step 3: 让状态回包至少携带可判断航向与底座状态是否正常的字段**

- [ ] **Step 4: 确认联合语义成立：主车持续读视觉，主车持续发控制，辅车持续执行，两车各自维持航向角**

## Task 4: 为已落地的纯逻辑边界补 TDD 保护（此时才进入 TDD 主段）

**Files:**
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/master/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_hw_motors.py`

- [ ] **Step 1: 为主车入口与装配规则写失败测试**

```python
def test_master_runtime_loop_uses_full_hw_bundle_owner():
    runtime = build_runtime()
    assert "imu" in runtime.hw_bundle
    assert "encoders" in runtime.hw_bundle
```

- [ ] **Step 2: 运行对应测试，确认在新实现收口前会失败或缺失**

Run: `python3 -m pytest tests/unit/master/test_app.py -q`
Expected: FAIL 或缺少行为保护。

- [ ] **Step 3: 只对纯逻辑边界补最小实现或整理，不重写板端主链**

- [ ] **Step 4: 为辅车入口、完整装配、状态回包与控制语义写失败测试**

- [ ] **Step 5: 运行对应测试，确认失败原因正确**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: FAIL，暴露缺失的纯逻辑保护。

- [ ] **Step 6: 只补最小实现，让测试通过**

- [ ] **Step 7: 为 IMU / 编码器 / 里程 / 航向角闭环中的纯算法部分补失败测试**

- [ ] **Step 8: 运行并修到通过**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/assistant/test_motion_runtime.py -q`
Expected: PASS。

## Task 5: 做三层板端验证与留证（完成判据以板上为准）

**Files:**
- Modify: `tools/run_stage2_smoke.py`
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`

- [ ] **Step 1: 重写 Stage 2 / HIL 口径，明确三层验证边界**

```text
- 主车独立层：可烧录、可启动、可维持主循环、可读取 IMU/编码器/底座状态、默认保持自身航向角
- 辅车独立层：可烧录、可启动、可接收控制、可读取 IMU/编码器/底座状态、默认保持自身航向角
- 联合链路层：主车读视觉、主车发控制、辅车执行随动、两车各自保持航向角
```

- [ ] **Step 2: 主机侧最终联合回归**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **Step 3: 主车独立 Stage 2 smoke**

Run: `python3 tools/run_stage2_smoke.py --port <master-port> --source-dir src/master`
Expected: 主车独立 smoke 成功。

- [ ] **Step 4: 辅车独立 Stage 2 smoke**

Run: `python3 tools/run_stage2_smoke.py --port <assistant-port> --source-dir src/assistant`
Expected: 辅车独立 smoke 成功。

- [ ] **Step 5: 主车独立 HIL 留证**

- [ ] **Step 6: 辅车独立 HIL 留证**

- [ ] **Step 7: 联合链路 HIL 留证**

## 完成标准

- `src/master` 与 `src/assistant` 都能直接作为 RT1021 根目录烧录并启动
- 主辅两边都接回 `IMU + 编码器 + 里程 + 航向角闭环` 完整底座主数据链
- 主车持续读视觉并向辅车发控制，辅车持续执行随动
- 两车在正常运行分支上电后都默认维持自身航向角
- 纯逻辑边界有主机侧 TDD 保护
- 板端三层验证与留证完成后，才允许说“完整系统可跑”
