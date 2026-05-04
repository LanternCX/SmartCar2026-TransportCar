# 主辅统一绕行模式实施计划

> 执行状态: Draft  
> **给执行 Agent:** 必须使用 `superpowers:subagent-driven-development` 按任务执行。步骤使用 checkbox 追踪。中间 Task 不做单独 Review, 所有 Task 完成后只做一次总 Review。

**目标:** 在共享底盘中新增一套统一绕行运动解算模式, 让主车和辅车都通过“目标角度 + 半径倍率”完成绕行, 保留旧 `rear only` 的角速度目标行为, 用半径倍率解出线速度, 并用这套模式替代旧 `rear only` 绕行用途, 同时保持主车流程前后行为不变。

**架构:** 共享底盘新增统一绕行 solver。角色层不再直接给绕行专用 `x / y / omega`, 而是只给目标角度和半径倍率。共享底盘继续沿用旧 `rear only` 的角速度目标链路生成 `omega_cmd`, 再把正数半径倍率解算为线速度 `v_cmd`, 最后把 `v_cmd + omega_cmd` 送入现有底盘控制链和三轮逆运动学执行。主车与辅车共用同一底盘入口, 状态同步链路保持现有语义。

**技术栈:** MicroPython 兼容 Python 代码, `pytest`, 现有 `src/core/runtime.py`, `src/vision/master`, `src/vision/assistant`, `src/config/params.py`。

---

## 关联 Spec

- `docs/superpowers/specs/2026-05-04-unified-orbit-mode-spec.md`

## 前置状态

- 当前错误方向的 orbit 改动已经通过 git 回退。
- 当前工作区基线干净, 后续实现从基线重新开始。
- 本 Plan 的正常开发流程不包含开发文档同步任务。
- 开发文档同步只作为最后手动触发 Task 预留。

## 执行约束

- 不把旧 `rear only` 继续当成新模式名。
- 不把绕行接口扩成 `x / y / omega` 外部调参接口。
- `radius_scale` 只允许正数, 只表达半径大小, 不承担方向语义。
- 绕行方向完全由旧 `rear only` 角速度目标链路决定。
- 不新增主车全局状态。
- 不新增辅车绕行完成回报。
- 不引入底盘半径、轮距或车体几何尺寸计算。
- 参数统一集中到 `src/config/params.py`。
- 行为改动按 RED -> GREEN -> REFACTOR 执行。
- 参数测试动态读取参数模块当前值, 不写死具体参数值。
- 中间 Task 不单独做 Review, 只在全部 Task 完成后做一次总 Review。
- 不执行 git 操作, 除非用户再次明确允许。
- Plan 只做 Subagent Driven Development 编排, 不写代码。
- 开发文档改动不纳入 Task 1 到 Task 4 的执行流程。
- 只有用户在代码验证通过后明确要求时, 才执行最后的文档同步 Task。

## 文件职责

- 修改: `src/config/params.py`  
  增加主车绕行半径倍率参数, 保持主辅绕行参数集中管理。
- 修改: `src/core/runtime.py`  
  新增统一绕行运动解算模式入口, 负责“沿用旧角速度目标链路生成 `omega_cmd` + 半径倍率解算 `v_cmd` -> 底盘执行”的内部调用链, 并替代旧 `rear only` 绕行用途。
- 修改: `src/vision/master/forward_runtime.py`  
  主车进入 `ORBITING` 时改为调用统一绕行模式入口, 并在收到辅车 `TARGET_FOUND` 后下发 `ASSISTANT_ORBIT`。
- 修改: `src/vision/master/state_machine.py`  
  保持主车状态切换顺序不变, 补足辅车绕行同步请求出口。
- 修改: `src/vision/assistant/state_machine.py`  
  增加 `ASSISTANT_ORBIT` 子状态。
- 修改: `src/vision/assistant/follow_runtime.py`  
  辅车收到 `ASSISTANT_ORBIT` 后调用统一绕行模式入口, 清空输入与待发项, 并在绕行期间忽略速度输入。
- 修改: `tests/unit/core/test_runtime_public_api.py`  
  覆盖统一绕行模式入口、参数读取、半径语义和停止收口。
- 修改: `tests/unit/core/runtime_support.py`  
  如有必要, 补齐统一绕行模式测试桩。
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`  
  覆盖主车绕行入口替换和辅车绕行同步链路。
- 修改: `tests/unit/vision/test_master_state_machine.py`  
  覆盖主车状态机在现有顺序下产生辅车绕行请求。
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`  
  覆盖辅车接收 `ASSISTANT_ORBIT`、调用统一绕行模式、清空输入和忽略速度包。
- 修改: `tests/unit/runtime/assistant_follow_runtime_support.py`  
  如有必要, 记录辅车对统一绕行模式入口的调用。
- 手动触发修改: `docs/developer/state.md`  
  同步主辅绕行状态与状态切换口径。
- 手动触发修改: `docs/developer/control.md`  
  同步统一绕行模式的输入语义、单位半径基准与底盘内部解算口径。
- 手动触发修改: `docs/developer/protocol.md`  
  同步 `ASSISTANT_ORBIT` 状态同步语义与主辅 ACK 口径。
- 手动触发修改: `docs/developer/vision.md`  
  同步主辅角色层在统一绕行模式下的职责边界与调用关系。

## Task 1: 共享底盘统一绕行运动解算模式

**涉及文件:**
- 修改: `src/config/params.py`
- 修改: `src/core/runtime.py`
- 测试: `tests/unit/core/test_runtime_public_api.py`
- 可能修改: `tests/unit/core/runtime_support.py`

- [ ] **步骤 1: 写失败测试: 参数入口与模式入口语义**
  - 覆盖主车和辅车绕行半径倍率参数存在且为有效正数。
  - 覆盖共享底盘暴露统一绕行模式入口, 不再使用辅车专属命名。
  - 覆盖统一绕行模式入口接收目标角度和半径倍率, 不对角色层暴露绕行专用 `x / y / omega` 调参语义。

- [ ] **步骤 2: 写失败测试: 保留旧 omega 行为并按半径解算线速度**
  - 固定旧 `rear only` 角速度控制输出, 覆盖统一绕行模式会保留相同的 `omega_cmd` 目标行为。
  - 覆盖统一绕行模式只根据半径倍率解算线速度 `v_cmd`, 不再向外暴露第二个自由调参量。
  - 覆盖半径倍率变化会影响最终绕行体感半径, 且保持单调关系。
  - 覆盖统一绕行模式内部最终仍走现有三轮逆运动学链路。

- [ ] **步骤 3: 写失败测试: 到达目标后停止收口**
  - 覆盖统一绕行模式在达到角度容差后关闭锁定、清零输出并停止电机。
  - 覆盖旧 `rear only` 绕行用途已经被统一绕行模式替代, 不再作为主车绕行的正式入口。

- [ ] **步骤 4: 实现共享底盘统一绕行模式**
  - 增加 `MASTER_ORBIT_RADIUS_SCALE`。
  - 在共享底盘中新增统一绕行模式入口与内部 solver 状态。
  - 建立“目标角度 + 半径倍率 -> 复用旧 `rear only` 角速度目标链路生成 `omega_cmd` -> 解算线速度 `v_cmd` -> 底盘控制链 -> 三轮逆运动学”的调用链。
  - 保留旧 `rear only` 作为单位半径标定语义参考, 但不再作为正式绕行模式名和主车绕行用途。

- [ ] **步骤 5: 验证 Task 1**
  - 运行 `tests/unit/core/test_runtime_public_api.py`。
  - 预期通过。

## Task 2: 主车切换到统一绕行模式并保持前后流程不变

**涉及文件:**
- 修改: `src/vision/master/forward_runtime.py`
- 修改: `src/vision/master/state_machine.py`
- 测试: `tests/unit/runtime/test_master_forward_runtime.py`
- 测试: `tests/unit/vision/test_master_state_machine.py`

- [ ] **步骤 1: 写失败测试: 主车进入 ORBITING 时调用统一绕行模式**
  - 覆盖主车收到辅车 `IDLE` ACK 后, 进入 `ORBITING` 的时机不变。
  - 覆盖主车在这个时机调用统一绕行模式入口, 而不是旧 `rear only` 绕行入口。
  - 覆盖主车读取 `MASTER_ORBIT_TARGET_DEG` 与 `MASTER_ORBIT_RADIUS_SCALE`。
  - 覆盖主车绕行方向仍由旧 `rear only` 角速度目标行为决定。

- [ ] **步骤 2: 写失败测试: 主车绕行前后行为不变**
  - 覆盖主车寻找、停辅车、主车绕行、主车绕行完成后下发 `ASSISTANT_APPROACH_OBJECT` 的顺序不变。
  - 覆盖主车绕行完成判据仍按现有完成语义推进。

- [ ] **步骤 3: 写失败测试: 主车收到辅车 TARGET_FOUND 后下发 ASSISTANT_ORBIT**
  - 覆盖主车回复 ACK。
  - 覆盖主车记录回报。
  - 覆盖主车创建 `ASSISTANT_ORBIT` 同步请求并按现有可靠机制重发, 收到 ACK 后停止。

- [ ] **步骤 4: 实现主车接入与同步链路**
  - 主车 `ORBITING` 改为调用统一绕行模式入口。
  - 主车状态机保持现有顺序, 只增加辅车绕行同步请求出口。
  - 保留现有 `ASSISTANT_IDLE`、`ASSISTANT_APPROACH_OBJECT`、`ASSISTANT_ORBIT` 的同步语义。

- [ ] **步骤 5: 验证 Task 2**
  - 运行 `tests/unit/vision/test_master_state_machine.py` 与 `tests/unit/runtime/test_master_forward_runtime.py`。
  - 预期通过。

## Task 3: 辅车接入统一绕行模式

**涉及文件:**
- 修改: `src/vision/assistant/state_machine.py`
- 修改: `src/vision/assistant/follow_runtime.py`
- 测试: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 可能修改: `tests/unit/runtime/assistant_follow_runtime_support.py`

- [ ] **步骤 1: 写失败测试: 辅车接受 ASSISTANT_ORBIT 子状态**
  - 覆盖 `ASSISTANT_ORBIT` 被接受并记录。
  - 覆盖该状态继续使用 `state=3`, `target=1`, `arg=0`。

- [ ] **步骤 2: 写失败测试: 辅车收到 ASSISTANT_ORBIT 后调用统一绕行模式**
  - 覆盖辅车 ACK。
  - 覆盖辅车清空两路速度缓存和本地待发项。
  - 覆盖辅车读取 `ASSISTANT_ORBIT_TARGET_DEG` 与 `ASSISTANT_ORBIT_RADIUS_SCALE`。
  - 覆盖辅车调用统一绕行模式入口, 而不是直接写绕行专用速度量。
  - 覆盖辅车绕行方向仍由旧 `rear only` 角速度目标行为决定。

- [ ] **步骤 3: 写失败测试: 绕行期间忽略速度输入且不回报完成**
  - 覆盖绕行期间 `UART8` 与 `UART6` 速度输入不会覆盖当前绕行。
  - 覆盖达到目标后本地停止。
  - 覆盖不会新增辅车绕行完成回报。

- [ ] **步骤 4: 实现辅车接入**
  - 新增 `ASSISTANT_ORBIT` 子状态。
  - 辅车收到同步后调用统一绕行模式入口。
  - 在绕行期间屏蔽速度包写入并保持等待后续同步。

- [ ] **步骤 5: 验证 Task 3**
  - 运行 `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`。
  - 预期通过。

## Task 4: 总验证与总 Review

**涉及文件:**
- 检查: `src/config/params.py`
- 检查: `src/core/runtime.py`
- 检查: `src/vision/master/state_machine.py`
- 检查: `src/vision/master/forward_runtime.py`
- 检查: `src/vision/assistant/state_machine.py`
- 检查: `src/vision/assistant/follow_runtime.py`
- 检查: 相关测试文件

- [ ] **步骤 1: 运行目标测试集**
  - 覆盖共享底盘、主车角色层、辅车角色层和同步链路的目标测试。

- [ ] **步骤 2: 运行完整单元测试**
  - 覆盖全部 `tests/unit`。

- [ ] **步骤 3: 运行契约测试**
  - 覆盖全部 `tests/contract`。

- [ ] **步骤 4: 做一次总 Review**
  - 检查是否满足 Spec。
  - 检查主车流程顺序没有变化。
  - 检查新模式已经替代旧 `rear only` 绕行用途。
  - 检查没有新增主车全局状态。
  - 检查没有新增辅车绕行完成回报。
  - 检查没有把绕行接口扩成 `x / y / omega` 外部调参接口。
  - 检查 `radius_scale` 只承担正数半径大小语义, 不承担方向语义。
  - 检查统一绕行模式保留了旧 `rear only` 的 `omega_cmd` 目标行为。
  - 检查没有引入底盘几何尺寸计算。

- [ ] **步骤 5: 暂停开发文档改动**
  - 本轮代码验证通过时, 不修改开发文档。
  - 保持 Spec 和 Plan 为 `Draft`, 等待用户后续指令。

## Task 5: 手动触发文档同步

**执行条件:** 只有用户在代码验证通过后明确要求补全文档时执行。

**涉及文件:**
- 修改: `docs/developer/state.md`
- 修改: `docs/developer/control.md`
- 修改: `docs/developer/protocol.md`
- 修改: `docs/developer/vision.md`

- [ ] **步骤 1: 更新状态文档**
  - 补充主车与辅车统一绕行模式涉及的状态语义。
  - 说明主车流程顺序不变, 辅车仍由 `ASSISTANT_ORBIT` 子状态承接绕行。

- [ ] **步骤 2: 更新控制文档**
  - 补充统一绕行运动解算模式。
  - 写明该模式对外只暴露“目标角度 + 半径倍率”。
  - 写明 `radius_scale = 1.0` 是旧 `rear only` 的单位半径基准。
  - 写明共享底盘保留旧 `rear only` 的 `omega_cmd` 目标行为, 再按半径倍率解出线速度。

- [ ] **步骤 3: 更新协议文档**
  - 补充 `ASSISTANT_ORBIT` 的同步语义。
  - 写明主车在收到辅车 `TARGET_FOUND` 后下发统一绕行同步, 并按现有可靠机制收口。

- [ ] **步骤 4: 更新视觉职责文档**
  - 补充主车和辅车角色层只负责状态编排、参数读取和统一绕行入口调用。
  - 写明角色层不直接暴露绕行专用 `x / y / omega` 调参接口。

- [ ] **步骤 5: 文档规则检查**
  - 检查四份开发文档不带历史性口吻。
  - 检查四份开发文档与当前 Spec 保持一致。
  - 检查文档改动不扩展本轮代码边界。

- [ ] **步骤 6: 标记 Spec 和 Plan 状态**
  - 只有 Task 5 也完成后, 才把本 Plan 和关联 Spec 的执行状态改为 `Archive`。

## Plan 自检

- Spec 覆盖: Task 1 覆盖统一绕行 solver 与参数; Task 2 覆盖主车切换到底层统一模式且保持流程不变; Task 3 覆盖辅车接入 `ASSISTANT_ORBIT`; Task 4 覆盖总验证与总 Review; Task 5 预留文档同步规划, 但不纳入默认开发流程。
- 上下文完整性: 已在 Task 前置状态、文件职责和各任务目标中写明当前基线、替代关系和接口语义, 避免执行时丢失设计上下文。
- 占位扫描: 本 Plan 未发现占位内容。
- 类型一致性: 统一使用“统一绕行模式入口 / 目标角度 / 半径倍率 / `omega_cmd` / `v_cmd` / ASSISTANT_ORBIT”这一套命名语义, 不再把新模式称为 `rear only`。
- 约束检查: 本 Plan 不写代码; 文档同步任务只作手动触发预留, 不扩展默认开发流程和无关功能。
