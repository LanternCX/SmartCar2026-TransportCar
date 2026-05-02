# 主车 UART6 视觉速度跟随实施计划

> 执行状态: Archive
> 面向执行者: 使用 `superpowers:subagent-driven-development` 按任务执行; 每个任务完成后由编排者 review。Plan 只做编排, 不包含实现代码。
> 设计依据: `docs/superpowers/specs/2026-05-02-master-uart6-vision-velocity-follow-design.md`

**目标:** 让当前车端仓库的主车运行入口接收本车 `UART6` 视觉速度, 并在没有同拍 `UART3` 输入时驱动主车本地底盘跟随红色沙包。

**架构:** 主车角色层新增一条最小 `UART6` 视觉速度输入路径, 只解析 `v,<vx>,<vy>` 并缓存最近合法速度。角色层保持 `UART3` 同拍优先级和 `UART8` 前馈职责, `UART6` 视觉速度只写入主车本地底盘, 不参与主辅转发和状态事件链路。

**技术栈:** MicroPython、RT1021、ASCII 短包、pytest、`src/vision/master/forward_runtime.py`

---

## 1. 任务复杂度评估

本轮只修改当前车端仓库, 行为目标单一, 但涉及主车控制周期、串口读取和输入优先级。需要写独立 Spec / Plan, 并用 TDD 锁定串口读取边界和优先级。

## 2. 文件范围与职责

### 需要修改

- `src/vision/master/forward_runtime.py`
  - 初始化主车本车 `UART6`。
  - 非阻塞读取 `UART6` 行输入。
  - 解析并保存最近合法视觉速度。
  - 在角色层速度编排中使用视觉速度。
  - 保持 `UART3` 和 `UART8` 行为稳定。

- `tests/unit/runtime/test_master_forward_runtime.py`
  - 增加 `UART6` 工厂和假串口能力。
  - 覆盖视觉速度写入底盘、优先级、不转发、坏包和缓存边界。
  - 调整主车视觉输入装配相关断言。

- `docs/developer/protocol.md`
  - 收口主车本地 `UART6` 在本能力中的正式输入为 `v,<vx>,<vy>`。
  - 明确主车视觉速度不转发 `UART8`。

- `docs/developer/vision.md`
  - 说明当前仓库只消费视觉速度, 红色沙包识别和 P 环由视觉端负责。

- `docs/developer/control.md`
  - 说明主车本地底盘速度优先级: 当前拍 `UART3` 优先, 否则使用最近合法 `UART6` 视觉速度。

### 不修改

- `../SmartCar2026-Vision/**`
- `src/vision/assistant/**`
- `src/control/**`
- `src/core/**`
- `src/protocol/**`
- `src/hardware/uart_bus.py`

## 3. Task 1: 写主车 `UART6` 视觉速度行为测试

**目标:** 先用失败测试锁定主车只消费视觉速度这一条主线。

**文件:**

- 修改: `tests/unit/runtime/test_master_forward_runtime.py`

**步骤:**

- [ ] 扩展测试桩, 为主车运行时提供独立的假 `UART6`。
- [ ] 将主车视觉输入装配测试调整为“主车会装配本车 `UART6` 视觉速度输入”。
- [ ] 增加测试: `UART6` 收到 `v,1.0,-2.0` 后, 主车本地底盘收到 `vx=1.0`、`vy=-2.0`、`omega=0`。
- [ ] 增加测试: `UART6` 视觉速度不会写入 `UART8`。
- [ ] 增加测试: 同一控制拍内同时存在合法 `UART3` 和 `UART6` 速度时, 最终底盘速度采用 `UART3`, 且只有 `UART3` 速度被转发到 `UART8`。
- [ ] 增加测试: 没有新 `UART3` 输入时, 最近一条合法 `UART6` 视觉速度继续写入底盘。
- [ ] 增加测试: 未收到任何合法 `UART6` 视觉速度时, 主车不会主动写入视觉速度。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`。
- [ ] 确认新增测试失败, 且失败原因指向主车没有读取或消费 `UART6` 视觉速度。

## 4. Task 2: 实现主车 `UART6` 视觉速度输入

**目标:** 用最小实现让 Task 1 的行为测试通过。

**文件:**

- 修改: `src/vision/master/forward_runtime.py`

**步骤:**

- [ ] 在主车运行时初始化阶段创建本车 `UART6`。
- [ ] 为 `UART6` 增加独立输入缓存和最近合法视觉速度缓存。
- [ ] 在角色层单拍流程中读取 `UART6`。
- [ ] `UART6` 输入只接受 `v` 速度短包。
- [ ] `UART6` 合法速度只保存为本车视觉速度, 不立即转发。
- [ ] `UART6` 视觉速度写入底盘时, `omega` 固定为 `0`, `has_omega` 固定为 `False`。
- [ ] `UART3` 成功处理合法速度时标记当前拍由上游输入接管。
- [ ] 当前拍没有合法 `UART3` 速度时, 将最近合法 `UART6` 视觉速度写入主车本地底盘。
- [ ] 保持 `UART3` 速度转发到 `UART8` 的行为稳定。
- [ ] 保持 `UART8` 回传读取行为稳定。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`。
- [ ] 确认 Task 1 的新增测试通过。

## 5. Task 3: 补串口读取边界回归测试

**目标:** 明确主车 `UART6` 读取路径不会通过坏包、半包或异常拖长控制周期。

**文件:**

- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
- 修改: `src/vision/master/forward_runtime.py`

**步骤:**

- [ ] 增加测试: `UART6` 收到非速度短包时不写底盘、不转发、不抛异常。
- [ ] 增加测试: `UART6` 收到非法速度短包时不覆盖上一条合法视觉速度。
- [ ] 增加测试: `UART6` 收到半行输入时不处理该半行, 控制周期仍继续执行。
- [ ] 增加测试: `UART6` 输入缓存超过固定上限时会被清空并记录输入无效。
- [ ] 增加测试: `UART6` 读取异常时控制周期仍继续执行共享底盘 `step()`。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`, 确认新增测试先失败。
- [ ] 在 `forward_runtime.py` 中为 `UART6` 输入缓存增加固定上限。
- [ ] 在 `forward_runtime.py` 中补齐 `UART6` 解码失败、读取异常、非法行记录。
- [ ] 确认异常和非法输入只影响 `UART6` 路径, 不改变 `UART3` 与 `UART8` 行为。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`。

## 6. Task 4: 文档最小收口

**目标:** 让开发文档只表达当前仓库落地的主车视觉速度消费边界。

**文件:**

- 修改: `docs/developer/protocol.md`
- 修改: `docs/developer/vision.md`
- 修改: `docs/developer/control.md`

**步骤:**

- [ ] 在 `protocol.md` 中确认主车本地 `UART6` 的本轮车端输入为 `v,<vx>,<vy>`。
- [ ] 在 `protocol.md` 中确认主车视觉速度不转发 `UART8`。
- [ ] 在 `vision.md` 中确认当前仓库只消费视觉速度, 红色沙包识别与速度计算由 OpenART Vision master 提供。
- [ ] 在 `control.md` 中确认同拍 `UART3` 优先于 `UART6` 视觉速度。
- [ ] 在 `control.md` 中确认 `UART6` 视觉速度按最近合法包保持。
- [ ] 检查文档没有把 `s/a/r/o` 写成本轮车端验收前提。
- [ ] 检查文档没有历史性口吻。

## 7. Task 5: 全量验证与收口

**目标:** 确认当前仓库行为稳定, 且改动没有扩散到非目标链路。

**文件:**

- 验证当前仓库。

**步骤:**

- [ ] 运行主车运行时测试: `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`。
- [ ] 运行车端单元测试: `python3 -m pytest tests/unit -q`。
- [ ] 运行车端契约测试: `python3 -m pytest tests/contract -q`。
- [ ] 检查 `src/vision/assistant/**` 没有修改。
- [ ] 检查 `src/control/**` 和 `src/core/**` 没有修改。
- [ ] 检查 `../SmartCar2026-Vision/**` 没有修改。
- [ ] 检查 `UART3` 速度仍会转发 `UART8`。
- [ ] 检查 `UART6` 视觉速度不会转发 `UART8`。
- [ ] 检查没有新增主车 hook、可靠事件或状态切换实现。
- [ ] Review 通过后, 将本 Spec 和 Plan 的执行状态改为 `Archive`。
- [ ] 如需要提交, 先向用户确认 commit message。

## 8. 板端联调记录项

- 主车切为 master 车号。
- OpenART Vision master 连到主车本车 `UART6`。
- 串口确认视觉端输出 `v,<vx>,<vy>`。
- 无 `UART3` 输入时, 主车底盘按视觉速度运动。
- 视觉端发送 `v,0,0` 时, 主车底盘停止平移。
- 同时给 `UART3` 输入速度时, 主车底盘优先响应 `UART3`。
- 辅车侧不应收到由主车视觉 `UART6` 产生的 `UART8` 速度包。
- 观察主车控制周期指示灯, 确认接入 `UART6` 后无明显周期拖长。
