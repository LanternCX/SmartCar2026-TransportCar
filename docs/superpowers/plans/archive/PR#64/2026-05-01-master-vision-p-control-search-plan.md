# 主车视觉端 P 环搜索控制实施计划

> 执行状态: Archive
> 面向执行者: 使用 `superpowers:subagent-driven-development` 按任务执行。本计划只做编排, 不包含代码。
> 设计依据: `docs/superpowers/specs/archive/PR#64/2026-05-01-master-vision-p-control-search-design.md`

**目标:** 让 OpenART Vision master 在视觉端完成主车搜索 P 环, 通过 `v,<vx>,<vy>` 下发搜索速度, 主车 RT1021 只负责状态、可靠事件和速度入口优先级。

**架构:** 主车 `UART6` 继续承载 `s/a/r` 可靠 hook 链路, 同时增加 OpenART Vision master 到 RT1021 的 `v` 搜索速度数据流。视觉端用识别框中心点 `x / y` 计算速度, 车端在 `SEARCH_OBJECT` 中消费该速度包并驱动共享底盘。

**技术栈:** MicroPython, OpenART, RT1021, ASCII 短包协议, pytest, `src/vision/master/`, `../SmartCar2026-Vision/master/`

---

## 1. 文件范围与职责

### 车端仓库

- 修改: `docs/developer/protocol.md`
  - 登记主车 `UART6` 上的 `v` 搜索速度语义。
  - 说明主车搜索控制不依赖 `o` 观测包。
- 修改: `docs/developer/vision.md`
  - 说明 OpenART Vision master 负责识别框中心点 P 环和 `v` 输出。
- 修改: `docs/developer/control.md`
  - 说明 `SEARCH_OBJECT` 的速度来源和优先级。
- 修改: `docs/developer/state.md`
  - 说明主车状态机只维护上下文、事件和状态迁移。
- 修改: `src/config/params.py`
  - 清理或调整主车固定搜索速度参数, 避免车端继续承担主搜索速度控制。
- 修改: `src/vision/master/state_machine.py`
  - 保留状态、上下文、可靠序号和事件处理职责。
  - 移除或弱化固定搜索速度输出职责。
- 修改: `src/vision/master/forward_runtime.py`
  - 处理 `UART6` 主车视觉 `v` 包。
  - 在 `SEARCH_OBJECT` 中把主车视觉速度写入本车底盘。
  - 保持 `UART3` 优先级和 `UART8` 转发行为。
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
  - 覆盖主车视觉速度输入、优先级、停车和不转发行为。
- 修改: `tests/unit/vision/test_master_state_machine.py`
  - 覆盖状态机职责收口。
- 修改: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
  - 覆盖主车视觉 `v` 包语义和 `s/a/r` 可靠语义并存。

### 视觉仓库

- 修改: `../SmartCar2026-Vision/master/main.py`
  - 增加主车搜索 P 环参数。
  - 使用识别框中心点 `x / y` 生成 `v` 搜索速度。
  - 保持 `s/a/r` hook 事件链路。
  - 默认不周期输出 `o` 观测包。
- 修改: `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
  - 覆盖主车视觉 P 环、无目标搜索速度、死区、限幅和事件稳定判断。
- 修改: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
  - 覆盖 master 输出 `v` 搜索速度和可靠事件格式。
- 修改: `../SmartCar2026-Vision/README.md`
  - 更新 OpenART Vision master 的输出职责。

## 2. Task 1: 更新协议与开发文档

**目标:** 先让正式文档表达新的职责边界, 避免实现过程中出现协议双轨。

**文件:**

- `docs/developer/protocol.md`
- `docs/developer/vision.md`
- `docs/developer/control.md`
- `docs/developer/state.md`

**步骤:**

- [x] 在 `protocol.md` 的 `UART6` 链路说明中加入主车视觉 `v` 搜索速度数据流。
- [x] 在 `protocol.md` 的 `v` 包链路规则中说明 OpenART Vision master 使用 `v,<vx>,<vy>` 控制主车搜索速度。
- [x] 在 `protocol.md` 中说明主车搜索控制不依赖 `o` 观测包。
- [x] 在 `vision.md` 中说明 OpenART Vision master 的 P 环职责。
- [x] 在 `vision.md` 中说明误差来自识别框中心点 `x / y`, 不使用最小外接旋转矩形边长。
- [x] 在 `control.md` 中说明 `SEARCH_OBJECT` 的速度来源为主车视觉 `v` 包。
- [x] 在 `control.md` 中保留 `UART3` 优先级和 `OBJECT_FOUND` 停车语义。
- [x] 在 `state.md` 中说明主车状态机不计算视觉 P 环。
- [x] Review 文档, 确认只描述当前事实、没有双轨兼容说明。

**验证:**

- 文档改动不写硬约束测试。
- 人工检查上述四份文档的协议字段和职责描述一致。

## 3. Task 2: 视觉仓库 master 输出 `v` 搜索速度

**目标:** OpenART Vision master 建立上下文后, 每帧输出主车搜索速度控制量。

**文件:**

- `../SmartCar2026-Vision/master/main.py`
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**步骤:**

- [x] 写视觉 master 格式化 `v,<vx>,<vy>` 的失败测试。
- [x] 写无目标时输出配置搜索速度的失败测试。
- [x] 写有目标时按识别框中心点 `x / y` 生成 P 控制量的失败测试。
- [x] 写横向和纵向死区输出零量的失败测试。
- [x] 写 `vx / vy` 限幅的失败测试。
- [x] 写目标稳定判断使用识别框中心点误差的失败测试。
- [x] 写不需要最小外接旋转矩形或 `marker_span` 的失败测试。
- [x] 运行视觉仓库相关测试, 确认新增测试先失败且失败原因指向缺失行为。
- [x] 在 `master/main.py` 增加主车搜索 P 环参数和速度格式化入口。
- [x] 在 `master/main.py` 增加主车搜索控制量生成逻辑。
- [x] 调整图像处理流程, 让主循环输出 `v` 数据流并保留 `s/a/r` 可靠事件。
- [x] 保持可靠包发送延时只作用于 `s/a/r`, 不作用于 `v` 数据流。
- [x] 运行视觉仓库单元和契约测试。

**验证命令:**

- `cd ../SmartCar2026-Vision && python3 -m pytest tests/unit/test_master_hook_protocol.py -q`
- `cd ../SmartCar2026-Vision && python3 -m pytest tests/contract/test_main_vision_protocol_contract.py -q`
- `cd ../SmartCar2026-Vision && python3 -m pytest tests/unit tests/contract -q`

## 4. Task 3: 车端主车角色层消费 `UART6` 视觉速度

**目标:** 主车 RT1021 在搜索态消费 OpenART Vision master 下发的 `v` 速度包。

**文件:**

- `src/vision/master/forward_runtime.py`
- `src/vision/master/state_machine.py`
- `src/config/params.py`
- `tests/unit/runtime/test_master_forward_runtime.py`
- `tests/unit/vision/test_master_state_machine.py`

**步骤:**

- [x] 写 `UART6` 收到 `v` 包后在 `SEARCH_OBJECT` 中写入本车底盘的失败测试。
- [x] 写主车视觉 `v` 包不转发到 `UART8` 的失败测试。
- [x] 写同拍 `UART3` 速度包优先于主车视觉 `v` 包的失败测试。
- [x] 写 `OBJECT_FOUND` 状态忽略主车视觉 `v` 并输出零平移速度的失败测试。
- [x] 写没有主车视觉速度时搜索态不使用车端固定搜索速度的失败测试。
- [x] 写状态机不持有主搜索 P 控制职责的失败测试。
- [x] 运行车端相关测试, 确认新增测试先失败且失败原因指向缺失行为。
- [x] 在主车角色层解析和记录最新主车视觉 `v` 包。
- [x] 调整搜索态速度写入逻辑, 使用主车视觉速度作为搜索速度来源。
- [x] 保留 `UART3` 输入优先级、`UART8` 遥控前馈转发和 `OBJECT_FOUND` 停车行为。
- [x] 清理车端固定搜索速度参数或将其移出主搜索控制路径。
- [x] 运行车端单元测试。

**验证命令:**

- `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`
- `python3 -m pytest tests/unit/vision/test_master_state_machine.py -q`
- `python3 -m pytest tests/unit -q`

## 5. Task 4: 协议契约与 README 收口

**目标:** 两个仓库的契约测试和说明文档与新链路一致。

**文件:**

- `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
- `../SmartCar2026-Vision/README.md`
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**步骤:**

- [x] 在车端契约测试中覆盖主车视觉 `v` 包仍使用通用速度短包解析。
- [x] 在车端契约测试中覆盖 `s/a/r` 与主车视觉 `v` 数据流并存。
- [x] 更新视觉 README 中 OpenART Vision master 的职责说明。
- [x] 更新视觉契约测试中 master 输出口径。
- [x] 运行两个仓库契约测试。

**验证命令:**

- `python3 -m pytest tests/contract -q`
- `cd ../SmartCar2026-Vision && python3 -m pytest tests/contract -q`

## 6. Task 5: 联合验证与板端准备

**目标:** 确认主机侧行为闭环, 并整理板端联调需要观察的结果。

**文件:**

- 车端仓库测试与文档。
- 视觉仓库测试与 README。

**步骤:**

- [x] 运行车端单元测试。
- [x] 运行车端契约测试。
- [x] 运行视觉仓库单元测试。
- [x] 运行视觉仓库契约测试。
- [x] 检查主车视觉 `v` 不转发 `UART8`。
- [x] 检查主车 `OBJECT_FOUND` 会覆盖视觉速度并停车。
- [x] 检查主车视觉 P 环未使用最小外接旋转矩形边长。
- [x] 检查 `v` 数据流发送路径没有可靠包延时。
- [x] 检查 `s/a/r` 可靠包发送路径仍有固定保护延时。
- [x] 准备板端联调记录项: 串口 `s/a/v/r/a` 顺序、无目标搜索速度、目标偏移时速度方向、目标进入窗口、`TARGET_FOUND` 确认、主车停车。

**验证命令:**

- `python3 -m pytest tests/unit tests/contract -q`
- `cd ../SmartCar2026-Vision && python3 -m pytest tests/unit tests/contract -q`

## 7. 风险与确认项

- 主车视觉 `vx / vy` 的正负号依赖相机安装和车体系方向, 板端联调必须确认。
- 无目标搜索速度由视觉端输出, 参数需要现场确认速度大小和方向。
- `v` 作为主车搜索控制输入时, 主车 RT1021 不通过 `o` 观测包计算搜索 P 环。
- 如果串口丢包导致主车持续使用旧视觉速度, 需要在后续单独设计超时清空策略。
- 本轮不实现物体锁定、精对齐、绕行、让位和搬运切入。
- 本轮不改变辅车视觉跟随链路。

## 8. 完成后状态处理

- 实施完成并通过 review 后, 将本 Plan 的执行状态改为 `Archive`。
- 对应 Spec 同步改为 `Archive`。
- 不执行 git commit, 除非用户在完成改动后明确确认 commit 消息。
