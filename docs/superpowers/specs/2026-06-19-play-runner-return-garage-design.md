# Play 播放器与回库 Play 设计

> 执行状态: Review
> 日期: 2026-06-19

## 目标

建立一个轻量 Play 播放机制, 让车端在固定流程阶段由 Play 临时接管运动输出。回库阶段作为第一条 Play 流程落地: 主车和辅车分别使用独立 Play 类, 按固定动作序列运行。视觉仓库 v2 入口下掉回库黄线跟随, 只保留黄线判据给车端 Play 使用。

## 背景

回库阶段流程固定, 但动作数量较多, 主车和辅车动作方向不同。把每一步都展开到主状态机和运行时分支中, 会让状态跳转、底盘动作、视觉判据和主辅差异混在一起。

Play 机制用于承载这类固定动作流程。状态机只负责决定什么时候启动 Play 和等待 Play 结果, Play 负责在一段时间内接管本车运动。

## 范围

本设计覆盖:

- Play 基础对象和步骤状态结构。
- Play 播放器的单 Play 接管规则。
- 位置式步骤和速度式步骤的执行语义。
- `until` 回调函数的只读边界。
- Play 相关模块、类和运行时接入边界。
- 主车回库 Play 和辅车回库 Play 的流程。
- Play 接管期间视觉输入与底盘输出的隔离规则。
- 视觉仓库 v2 回库黄线判据和事件输出边界。
- 视觉仓库 v2 回库黄线跟随速度能力下线。

本设计不覆盖:

- 动态脚本语言或字符串注册表。
- 多个 Play 同时运行。
- Play 抢占、暂停、恢复和队列排队。
- 自动停车判定。
- 让视觉速度在 Play 接管期间直接控制底盘。
- 保留视觉仓库回库黄线跟随速度接口。
- 在视觉仓库内实现 Play 播放器。
- 视觉仓库旧入口 `main.py` 的回库黄线跟随清理。

## 总体设计

Play 是一个独立流程类。每个 Play 文件只描述一个明确流程, 一个 Play 类只服务一个明确角色。主车回库和辅车回库分别写成两个 Play 类, 不在 Play 内部判断主车或辅车。

Play 调用方只以具体 Play 类作为参数请求播放。调用方不传字符串, 不直接拼动作步骤, 不管理步骤下发细节。

Play 播放器持有当前正在播放的 Play 对象。同一时间只允许一个 Play 接管本车运动。已有 Play 正在运行时, 新的 Play 请求直接拒绝。

## 代码结构设计

Play 机制集中放在 `src/play/` 包内。播放器框架直接放在 `src/play/` 下, 具体 Play 放在 `src/play/routines/` 下, 不接管主辅状态机、通信协议或底盘基础控制。

建议模块边界:

```text
src/play/
  __init__.py                # 暴露对外最小入口
  base.py                    # BasePlay、Play 状态、单步结果
  runner.py                  # PlayRunner, 维护当前正在播放的 Play
  context.py                 # PlayContext, 暴露受限底盘动作和条件查询入口
  steps.py                   # 位置式步骤、速度式步骤、保持步骤
  conditions.py              # 通用只读回调函数辅助结构
  routines/
    __init__.py
    master_return_garage.py  # 主车回库 Play
    assistant_return_garage.py # 辅车回库 Play
```

核心对象职责:

```text
BasePlay
  _steps                     # 私有步骤序列
  state                      # 未开始 / 运行中 / 保持中 / 完成 / 失败
  step_index                 # 当前步骤序号
  last_result                # 最后一次播放结果
  tick(ctx)                  # 推进当前步骤一拍

PlayRunner
  current_play               # 当前正在播放的 Play 对象
  run(play_class)            # 启动指定 Play
  tick(ctx)                  # 推进当前 Play 一拍
  reject_if_busy             # 已有 Play 时直接拒绝
  release_when_finished      # Play 完成后释放 current_play

PlayContext
  set_position_x / y         # 下发位置式目标
  set_angle                  # 下发角度目标
  write_velocity             # 写入固定速度
  motion_done                # 查询底盘目标是否完成
  yellow_line_ready          # 查询黄线判据是否满足

Step
  state                      # 未进入 / 已下发 / 等待完成 / 已完成 / 失败
  enter(ctx)                 # 一次性进入动作
  tick(ctx)                  # 每拍动作
  done(ctx)                  # 完成判断

until callback
  fn(ctx) -> bool            # 每拍调用的只读回调函数
```

回库 Play 结构:

```text
MasterReturnGaragePlay
  local constants:
    RETURN_FORWARD_SPEED = 5
    FINAL_FORWARD_SPEED = 3

  _steps:
    AngleStep(+90)
    VelocityYStep(RETURN_FORWARD_SPEED, until=yellow_line_ready)
    AngleStep(-90)
    HoldVelocityYStep(FINAL_FORWARD_SPEED)

AssistantReturnGaragePlay
  local constants:
    ASSISTANT_LEAD_DISTANCE = 30cm 对应的 core 位置单位值
    RETURN_FORWARD_SPEED = 5
    FINAL_FORWARD_SPEED = 3

  _steps:
    PositionYStep(ASSISTANT_LEAD_DISTANCE)
    AngleStep(-90)
    VelocityYStep(RETURN_FORWARD_SPEED, until=yellow_line_ready)
    AngleStep(-90)
    HoldVelocityYStep(FINAL_FORWARD_SPEED)
```

具体 Play 类只声明自己的私有步骤序列。主车回库 Play 和辅车回库 Play 分别使用独立类, 不共享同一个带角色分支的 Play。

角度步骤符号约定:

- `AngleStep(+90)` 表示向右转 90 度。
- `AngleStep(-90)` 表示向左转 90 度。

播放器框架和具体 Play 不平铺在同一目录。新增其他 Play 时, 在 `src/play/routines/` 下新增单独文件, 不把业务 Play 文件放回 `src/play/` 根目录。

视觉仓库本轮只调整 OpenART v2 入口的黄线判据和协议输出, 不承载车端 Play 状态, 不再提供回库黄线跟随速度:

```text
../SmartCar2026-Vision/
  master/main_v2.py                  # 主车回库黄线判据与事件输出
  assistant/main_v2.py               # 辅车回库黄线判据与事件输出
  tests/unit/test_master_main_v2.py
  tests/unit/test_assistant_main_v2.py
  tests/contract/test_main_v2_vision_protocol_contract.py
```

播放器 API 形态:

```text
play.run(play_class) -> PlayRunResult

输入:
  play_class                 # 具体 Play 类, 例如 MasterReturnGaragePlay

返回:
  PlayRunResult.accepted     # 本次请求是否被接受
  PlayRunResult.status       # started / rejected
  PlayRunResult.active       # 是否仍接管车端运动
  PlayRunResult.play_class   # 当前 Play 类
  PlayRunResult.reason       # rejected 时的原因

规则:
  current_play is None:
    创建 play_class 对象
    返回 started

  current_play is not None:
    不创建新 Play
    不改变 current_play
    返回 rejected
```

播放器推进 API 形态:

```text
play.tick(ctx) -> PlayRunResult

输入:
  ctx                        # 本拍执行上下文

返回:
  PlayRunResult.status       # idle / running / holding / finished / failed
  PlayRunResult.active       # 是否仍接管车端运动
  PlayRunResult.play_class   # 当前 Play 类

  current_play finished:
    释放 current_play
    返回 finished
```

状态机调用形态:

```text
start_result = play.run(MasterReturnGaragePlay)
tick_result = play.tick(play_context)

if tick_result.active:
    跳过普通状态速度输出
    下一拍继续 tick 当前 Play

if tick_result.status == finished:
    允许状态机进入下一个大状态

if start_result.status == rejected:
    不抢占正在播放的 Play
```

## Play 对象

每个 Play 对象至少维护以下状态:

- Play 运行状态: 未开始、运行中、保持中、完成、失败。
- 当前步骤序号。
- 当前步骤状态。
- 当前步骤是否已经执行进入动作。
- 最后一次结果, 用于日志、诊断和测试。

Play 类以私有步骤序列描述流程。步骤序列是 Play 类的固定结构, 不通过公开构建函数生成。新建 Play 时, 开发者只需要新建一个 Play 类并声明自己的私有步骤序列。

Play 不直接持有主车或辅车运行时对象。Play 的步骤执行通过受限上下文访问底盘动作入口, 并通过 `until` 回调函数读取切换条件。

## 步骤设计

步骤分为两类:

- 位置式步骤: `x`、`y`、`angle`。
- 速度式步骤: `vx`、`vy`、`w`。

位置式步骤语义:

- 进入步骤时只下发一次目标。
- 下发后等待底盘目标完成。
- 底盘目标完成后进入下一步。
- 重复 tick 不得重复下发同一目标。

速度式步骤语义:

- 每拍写入固定速度。
- 可以绑定只读 `until(ctx)` 回调函数。
- `until(ctx)` 返回真后进入下一步。
- 没有结束条件的速度式步骤进入保持态, 持续接管底盘输出。

步骤状态至少包含:

- 未进入。
- 已下发。
- 等待完成。
- 已完成。
- 失败。

## `until` 回调函数

`until` 回调函数只负责判断是否满足步骤切换条件。回调函数由具体 Play 文件引用或定义, 每拍由速度式步骤调用。回调函数可以读取:

- 视觉事件缓存。
- 黄线判据状态。
- 底盘完成状态。

回调函数不得:

- 写底盘速度。
- 下发位置目标。
- 修改状态机状态。
- 修改播放器当前 Play。
- 发起主辅通信。

回库黄线回调使用视觉侧“主车后退到黄线”的同一判据口径。Play 接管期间该判据只作为直走结束条件。

## 执行上下文

执行上下文是 Play 步骤使用的受限接口, 不保存 Play 状态。它只暴露 Play 需要的最小能力:

- 下发位置式目标。
- 写入固定速度。
- 查询底盘目标是否完成。
- 查询黄线判据是否满足。

执行上下文不提供角色判断接口。主车和辅车通过选择不同 Play 类表达流程差异。

## 视觉仓库边界

视觉仓库 v2 入口负责把回库黄线图像收敛成车端可缓存的判据输入。车端通过 `until(ctx)` 回调读取该判据。v2 回库黄线跟随速度计算、速度发送和对应测试口径直接下线。

黄线判据事件设计:

- 主车和辅车 v2 均使用 `RETURN_LINE_ALIGNED` 表示黄线 ready。
- `RETURN_LINE_ALIGNED` 事件编号沿用主车现有编号 `10`。
- 主车和辅车使用同一判据: 当前主车“后退到黄线”的完成判据。
- 车端只缓存黄线 ready 状态, 不区分该状态来自主车或辅车视觉内部的不同算法分支。

主车 OpenART 侧:

- 保留“主车后退到黄线”的判据口径, 作为主车回库 Play 直走步骤的结束条件来源。
- 黄线判据通过 `RETURN_LINE_ALIGNED` 可靠事件进入车端缓存。
- 删除回库黄线跟随速度输出。
- 回库停车完成事件不作为 Play 完成条件, 相关主流程和合同测试不保留为回库终点。

辅车 OpenART 侧:

- 使用和主车一致的黄线判据口径, 作为辅车回库 Play 直走步骤的结束条件来源。
- 黄线判据通过 `RETURN_LINE_ALIGNED` 可靠事件进入车端缓存。
- 删除回库黄线跟随速度输出。
- 本地回库完成事件不作为辅车停车条件, 相关主流程和合同测试不保留为回库终点。

## Play 播放器

Play 播放器在每台车运行时中各维护一个当前 Play 对象。

播放器规则:

- 没有 Play 时, 接受新的 Play 类请求并创建对象。
- 已有当前 Play 时, 直接拒绝后续所有 Play 请求。
- 当前 Play 只通过 `tick(ctx)` 推进。
- 当前 Play 处于运行中或保持中时, 车端运动由 Play 接管。
- 当前 Play 完成时, 播放器释放当前 Play。
- 当前 Play 进入保持态后不自动释放, 后续 `run(...)` 请求继续被拒绝。
- 当前 Play 失败时, 播放器返回失败结果, 由调用侧决定后续状态。

播放器不维护等待队列, 不自动抢占当前 Play, 不根据字符串查找 Play。

## 接管规则

Play 活跃期间, 普通状态机速度输出不得写入底盘。运行时在 Play 接管阶段只允许播放器向底盘写入运动目标或固定速度。

运行时不期待回库黄线速度包。若历史或异常速度包出现, 也不得在 Play 活跃期间写入底盘。视觉输入只能通过 `until` 回调函数影响步骤切换。

Play 保持态仍然视为接管状态。保持态中的固定速度继续由 Play 写入, 状态机不进入完成停车。

保持态不自动结束。进入保持态后, 播放器继续持有当前 Play, 不释放 `current_play`, 不接受新的 Play 请求。

## 回库 Play

### 主车回库 Play

主车在最后一次清障后退完成后进入主车回库 Play。

主车步骤:

1. 向右转 90 度。
2. 以速度 5 固定向前直走, 直到黄线判据满足。
3. 向左转 90 度。
4. 以速度 3 固定向前保持。

主车回库 Play 进入保持态后, 车端持续给定向前速度, 不进入完成停车状态。

### 辅车回库 Play

辅车收到主车同步后进入辅车回库 Play。

辅车步骤:

1. 按 core 位置单位固定向前移动 30cm 对应距离。
2. 向左转 90 度。
3. 以速度 5 固定向前直走, 直到黄线判据满足。
4. 向左转 90 度。
5. 以速度 3 固定向前保持。

辅车回库 Play 进入保持态后, 车端持续给定向前速度, 不根据本车视觉事件自行进入完成停车。

## 状态机边界

主车状态机继续负责全局任务主线:

- 判断最后一次清障后退完成。
- 发起主车回库 Play。
- 同步辅车进入辅车回库 Play。
- 在 Play 运行中等待播放结果。

辅车状态机继续接受主车同步:

- 收到回库 Play 同步后启动辅车回库 Play。
- Play 运行中由播放器接管本车运动。
- Play 保持态下持续保持固定向前速度。

Play 不负责全局任务计数, 不负责主辅同步, 不负责通信重试。

## 局部常量

回库 Play 的流程参数优先写在对应 Play 文件内, 作为 Play 局部常量。局部常量只服务该 Play, 不进入全局 `config/` 模块。

主车回库 Play 至少维护以下局部常量:

- 黄线前直走速度。
- 保持向前速度。

辅车回库 Play 至少维护以下局部常量:

- 前置固定移动距离。
- 黄线前直走速度。
- 保持向前速度。

具体数值:

- 黄线前直走速度: 5。
- 保持向前速度: 3。
- 辅车前置固定移动距离: 物理距离 30cm, 代码值使用 core 现有位置单位。

转向角度作为步骤表达的一部分直接写在 Play 步骤序列中。只有跨多个 Play 共享、或代表硬件事实和全局安全边界的参数才放入 `config/` 模块。

## 测试边界

Play 基础测试覆盖:

- 播放器没有当前 Play 时接受请求。
- 播放器已有当前 Play 时拒绝后续所有 Play 请求。
- `tick(ctx)` 推进当前 Play。
- 位置式步骤只下发一次目标。
- 速度式步骤每拍写固定速度。
- 速度式步骤条件满足后进入下一步。
- 保持步骤持续接管底盘。

回库 Play 测试覆盖:

- 主车回库 Play 的步骤顺序为右转、直走等黄线、左转、向前保持。
- 辅车回库 Play 的步骤顺序为固定前进、左转、直走等黄线、左转、向前保持。
- 黄线判据满足前直走步骤不结束。
- 黄线判据满足后进入转向步骤。
- 保持态不进入完成停车。
- 车端不消费回库黄线跟随速度。
- 视觉仓库主车回库黄线判据能触发车端 `until(ctx)` 条件。
- 视觉仓库辅车回库黄线判据能触发车端 `until(ctx)` 条件。
- 视觉仓库不再保留回库黄线跟随速度测试口径。
- 回库完成事件不参与车端回库控制主线。

状态机和运行时测试覆盖:

- 主车最后一次清障后退完成后启动主车回库 Play。
- 主车启动回库时同步辅车进入辅车回库 Play。
- Play 运行中普通状态速度输出被跳过。
- 有其他 Play 运行时新 Play 请求被拒绝。

## 完成判据

- 新建 Play 时只需要新增一个 Play 类并声明私有步骤序列。
- 播放器同一时间只持有一个当前 Play。
- Play 活跃期间车端运动由 Play 接管。
- 视觉输入在 Play 活跃期间只作为条件, 不直接写底盘。
- 视觉仓库 v2 入口只提供黄线判据输入, 不提供回库黄线跟随速度。
- 主车和辅车回库 Play 分别表达, 不在 Play 内部做角色分支。
- 回库左转或右转后进入固定向前保持, 不依赖停车判定。
