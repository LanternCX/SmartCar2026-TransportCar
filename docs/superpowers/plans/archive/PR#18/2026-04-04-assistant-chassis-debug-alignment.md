# 辅车底盘按主车 debug 基线对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `src/assistant` 当前正常上板运行链按主车已验证的底盘 debug 基线对齐，消除板端不存在依赖，统一采样、姿态、节拍与左右轮映射，并保持辅车现有职责不变。

**Architecture:** 直接在辅车当前主运行链上复用主车已经验证过的底盘基础实现。保持 `assistant.main -> assistant.app -> assistant.motion_runtime -> assistant.ctrl.* -> assistant.state` 的职责边界不变，只替换会影响板端兼容、姿态更新、航向保持、控制节拍和硬件映射的基础链。

**Tech Stack:** Python, pytest, MicroPython RT1021, HIL 留证

---

## 文件结构

### 计划修改文件

- `src/assistant/main.py`
  对齐辅车正常启动入口、控制周期驱动、采样触发链和最小运行观察点。
- `src/assistant/app.py`
  保持唯一 `hw_bundle` owner，并补齐平铺上传时的直接导入兼容。
- `src/assistant/motion_runtime.py`
  对齐底盘基础观测刷新、动态节拍、主动转动与保持接管、状态回包绑定和加载观察点。
- `src/assistant/ctrl/attitude.py`
  对齐姿态更新时间、航向保持积分、角速度阻尼和主动转动释放语义。
- `src/assistant/state/__init__.py`
  移除板端不稳类型依赖，并补齐对齐主车所需状态字段。
- `src/assistant/runtime_params.py`
  补齐与主车一致的稳定参数入口。
- `src/assistant/hw/encoders.py`
  对齐左右轮编码器映射和首次设备绑定语义。
- `src/assistant/hw/imu.py`
  对齐 IMU 首次设备绑定语义。
- `src/assistant/hw/uart.py`
  补齐平铺上传时的直接导入兼容。
- `src/assistant/status.py`
  补齐平铺上传时的直接导入兼容，保证最小状态回包链不断。
- `tests/unit/assistant/test_app.py`
  保护入口调度、capture ticker、启动 owner 和持续运行节拍。
- `tests/unit/assistant/test_motion_runtime.py`
  保护运行时导入兼容、主动/保持切换、动态节拍和加载观察点。
- `tests/unit/assistant/test_stability_baseline.py`
  保护姿态链、航向保持和主辅底盘基础行为一致性。
- `tests/unit/assistant/test_structure_runtime.py`
  保护辅车硬件映射事实与最小运行边界。
- `tests/unit/assistant/test_runtime_loop.py`
  保护辅车运行循环在三路编码器结构、唯一 owner 和 capture ticker 对齐后的入口行为。
- `tests/unit/assistant/test_runtime_params.py`
  保护新增稳定参数入口。
- `tests/unit/assistant/test_status.py`
  保护 `state_line()` 与最小状态回包边界在去掉板端不稳依赖后不变形。
- `tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md`
  记录人工联调、左右轮方向、航向保持、参数加载和动态节拍证据。

### 参考但不修改的文件

- `src/master/main.py`
- `src/master/motion_runtime.py`
- `src/master/ctrl/attitude.py`
- `src/master/runtime_params.py`
- `src/master/hw/motors.py`
- `src/master/hw/encoders.py`
- `src/master/hw/imu.py`
- `tests/hil/2026-04-03-master-heading-control-stage2-smoke.md`
- `tests/hil/2026-04-03-master-heading-control-stage3-manual.md`

### 参数入口说明

- 当前 `master` / `assistant` 现有主线已经把运行策略、阈值、控制周期和比例系数集中在各自的 `runtime_params.py`。
- 本轮任务目标是按主车现有已验证基线对齐辅车，不顺手重构整个参数入口。
- 因此本轮新增的稳定参数继续落在 `src/assistant/runtime_params.py`，与 `src/master/runtime_params.py` 保持同一现状口径。
- 若后续仓库统一推进参数入口迁移，应把 `master` / `assistant` 一起迁移，不在本轮辅车对齐任务里单边改口径。

## Task 1: 锁定辅车入口与板端兼容失败边界

**Files:**
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_status.py`
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/main.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/state/__init__.py`
- Modify: `src/assistant/hw/encoders.py`
- Modify: `src/assistant/hw/imu.py`
- Modify: `src/assistant/hw/uart.py`
- Modify: `src/assistant/status.py`

- [ ] **Step 1: 先写失败测试，固定板端兼容和入口语义**
  目标测试点：
  - `assistant.motion_runtime` 在禁用 `types` 的模拟环境下仍可导入。
  - `assistant.state` 在禁用 `typing` 的模拟环境下仍可导入。
  - 平铺上传场景下可以直接导入顶层 `app` 模块。
  - `_build_capture_ticker()` 会注册三路编码器和 IMU 设备。
  - 编码器首次 `ensure_device()` 会完成与主车一致的设备绑定。
  - IMU 首次 `ensure_device()` 会完成与主车一致的设备绑定。
  - `_start_runtime()` 会把 capture ticker / heartbeat 挂到 loop 上。
  - `state_line()` 仍保留当前最小状态回包语义。

- [ ] **Step 2: 运行测试，确认它们先失败**
  Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_runtime_loop.py tests/unit/assistant/test_status.py -q`
  Expected: 因 `types` / `typing` 依赖、平铺上传直导链不完整、缺少 capture ticker / heartbeat、或 IMU / 编码器绑定语义不一致而失败。

- [ ] **Step 3: 写最小实现，让辅车入口和板端兼容先过线**
  实现要求：
  - 删除 `MethodType` 依赖和仅为类型提示存在的板端不稳声明。
  - 去掉板端不稳依赖时，仍保留完整类型标注，不允许简单删空类型信息。
  - 补齐 `app.py`、`motion_runtime.py` 及其主链下游在平铺上传场景下的直接导入分支。
  - 把 `hw.uart.py` 和 `status.py` 一并纳入平铺上传直导链，不允许 `app.py` 直导通过、下游再断。
  - 在 `assistant.main` 中补齐 `_ticks_diff_ms`、`_noop_ticker_callback`、`_build_capture_ticker`、`_build_runtime_heartbeat_led`，并让 `_start_runtime()` 像主车一样挂载 capture ticker / heartbeat。
  - 在 `assistant.hw.encoders` 中补齐与主车一致的首次设备绑定语义。
  - 在 `assistant.hw.imu` 中补齐与主车一致的首次设备绑定语义。
  - 去掉 `MethodType` 后，`state_line()` 的绑定继续放在运行时装配阶段处理，不把状态模块重新耦回序列化模块。

- [ ] **Step 4: 重新运行测试，确认入口和导入边界通过**
  Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_runtime_loop.py tests/unit/assistant/test_status.py -q`
  Expected: PASS；辅车运行链可在禁用 `types` / `typing` 的模拟环境下导入，平铺上传导入链完整，入口测试可观察到 capture ticker 与 heartbeat 已挂载。

- [ ] **Step 5: 若用户要求提交，先准备提交说明**
  Run: `git status --short`
  Expected: 能清晰识别本任务改动；若用户要求提交，先确认 commit message，再执行提交。

## Task 2: 锁定姿态更新、稳定参数和加载观察口径

**Files:**
- Modify: `tests/unit/assistant/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_runtime_params.py`
- Modify: `src/assistant/runtime_params.py`
- Modify: `src/assistant/ctrl/attitude.py`
- Modify: `src/assistant/state/__init__.py`
- Modify: `src/assistant/motion_runtime.py`

- [ ] **Step 1: 先写失败测试，固定姿态链、稳定参数和加载观察口径**
  目标测试点：
  - `update_heading_from_gyro()` 与已验证姿态链口径一致。
  - 航向保持按真实时间累计积分，并包含角速度阻尼。
  - `create_runtime_state()` 读到 `yaw_kd` 与 `hold_speed_eps`。
  - `create_runtime_state()` 会输出 `ident_lookup_loaded` 摘要。
  - `create_runtime_state()` 会输出 `gyro_offsets_loaded` 摘要。

- [ ] **Step 2: 运行测试，确认当前辅车姿态链先失败**
  Run: `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_runtime_params.py -q`
  Expected: 因缺少 `YAW_KD`、`HOLD_SPEED_EPS`、`last_attitude_time_us`、真实时间积分或加载观察输出而失败。

- [ ] **Step 3: 写最小实现，让辅车姿态和航向保持对齐主车**
  实现要求：
  - 直接对齐主车当前可复用的姿态更新逻辑。
  - 在 `assistant.state.MotionRuntimeState` 中补齐 `yaw_kd`、`hold_speed_eps`、`last_attitude_time_us`。
  - 在 `assistant.motion_runtime.create_runtime_state()` 中对齐主车，把 `YAW_KD`、`HOLD_SPEED_EPS` 写入运行时状态。
  - 在 `assistant.motion_runtime.create_runtime_state()` 中补最小观察面，至少能通过启动日志或受控调试输出看到 `ident_lookup_loaded` 和 `gyro_offsets_loaded` 摘要。
  - 不引入新的兜底层，不增加与辅车职责无关的状态字段。

- [ ] **Step 4: 重新运行测试，确认姿态和稳定参数边界通过**
  Run: `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_runtime_params.py -q`
  Expected: PASS；辅车姿态更新已按真实时间推进，航向保持包含 tick 缩放和角速度阻尼，稳定参数入口与主车一致，且加载观察点可见。

- [ ] **Step 5: 若用户要求提交，先准备提交说明**
  Run: `git status --short`
  Expected: 能清晰识别本任务改动；若用户要求提交，先确认 commit message，再执行提交。

## Task 3: 锁定动态节拍贯穿与左右轮映射对齐

**Files:**
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/hw/motors.py`
- Modify: `src/assistant/hw/encoders.py`

- [ ] **Step 1: 先写失败测试，固定后半段节拍与映射事实**
  目标测试点：
  - 轮速控制器收到的 `dt_s` 与姿态链同拍。
  - 左右轮电机端口与方向位和主车一致。
  - 左右轮编码器引脚与方向位和主车一致。
  - 运行循环相关测试改成三路编码器结构后仍保持正确 owner 语义。

- [ ] **Step 2: 运行测试，确认当前后半段节拍和映射先失败**
  Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_runtime_loop.py -q`
  Expected: 因轮速控制仍未拿到真实 `dt`，或左右轮映射仍保留旧值而失败。

- [ ] **Step 3: 写最小实现，让动态节拍贯穿到底盘后半段并统一映射**
  实现要求：
  - 直接参考主车当前 `motion_runtime` 的 `hold` / `vel` 接管语义。
  - 确认 `wheel_controllers` 收到的 `dt_s` 与姿态链使用同一拍真实时间基准。
  - 映射事实一次性收口，不保留翻符号兜底。

- [ ] **Step 4: 重新运行测试，确认后半段节拍与映射通过**
  Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_runtime_loop.py -q`
  Expected: PASS；轮速控制使用与姿态链同拍的真实时间基准，辅车左右轮映射与主车完全一致。

- [ ] **Step 5: 跑辅车主机侧完整回归**
  Run: `python3 -m pytest tests/unit/assistant -q`
  Expected: PASS；辅车当前主机侧回归全部通过，没有把现有跟随、停机和回包边界带坏。

## Task 4: 执行 Stage 3 留证并完成设备侧收口

**Files:**
- Create: `tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md`
- Modify: `docs/superpowers/specs/2026-04-04-assistant-chassis-debug-alignment-design.md`（仅在执行时发现规格必须同步修正时）

- [ ] **Step 1: 写 Stage 3 人工联调留证模板**
  模板必须包含：
  - 主车对齐参考提交、步骤、预期、实测、结论、失败分类。
  - 运行时 owner / 内存自检项：新增常驻对象、唯一 owner、创建阶段、保留原因、`mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle`、`diag_survival`。
  - 必查项：左右轮方向、零漂文件存在、零漂实际加载、零漂结果合理、辨识参数文件存在、辨识参数实际加载、辨识参数合理、动态节拍证据覆盖到控制链关键环节、`health` / `tick` 等最小诊断面仍可用。
  - 必填证据：文件路径、启动日志中 `ident_lookup_loaded` / `gyro_offsets_loaded` 的原始文本、关键参数值摘要、步骤 / 预期 / 实测 / 结论。

- [ ] **Step 2: 运行关键交叉验证，确保主辅基础行为口径一致**
  Run: `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/master/test_stability_baseline.py -q`
  Expected: PASS；辅车和主车在共享基础链入口上不再出现已知偏差。

- [ ] **Step 3: 执行 Stage 3 人工联调，并把实测与结论填入留证文档**
  Run: `按 tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md 执行人工联调并填写实测结果`
  Expected: Stage 3 文档已明确记录左右轮方向、零漂加载、辨识参数加载、动态节拍证据、最小诊断面和最终结论，不留空模板。

- [ ] **Step 4: 做一次实现后自检**
  Run: `git diff -- tests/unit/assistant src/assistant tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md docs/superpowers/specs/2026-04-04-assistant-chassis-debug-alignment-design.md`
  Expected: 改动只覆盖辅车当前正常运行链、相关单测和留证文档；未扩散到主车、视觉或协议语义。

- [ ] **Step 5: 若用户要求提交，先准备最终提交说明**
  Run: `git status --short`
  Expected: 能清晰识别本轮改动；若用户要求提交，先向用户确认 commit message，再执行提交。

## 最终验证顺序

1. `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_structure_runtime.py tests/unit/assistant/test_runtime_loop.py tests/unit/assistant/test_runtime_params.py tests/unit/assistant/test_status.py -q`
2. `python3 -m pytest tests/unit/assistant -q`
3. `python3 -m pytest tests/unit/master/test_stability_baseline.py -q`
4. 按 `tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md` 做人工联调留证并填完结果

## 完成判据

- 辅车主运行链不再依赖板端不存在模块。
- 辅车入口已建立 capture ticker，并进入真实持续运行。
- 辅车平铺上传导入链完整，不会在 `app.py`、`hw.uart.py`、`status.py` 等下游边界断掉。
- 辅车姿态链、航向保持和后半段轮速控制使用同一拍真实时间基准。
- 辅车左右轮映射与主车一致。
- 辅车零漂校准结果和辨识参数不只存在，而且已确认加载的是有效结果。
- Stage 3 留证文档不是空模板，而是已经写入实测、失败分类和结论。
- 辅车仍保持现有跟随、停机与最小状态回传职责。
- 辅车主机侧测试通过，且设备侧人工联调留证已完成。
