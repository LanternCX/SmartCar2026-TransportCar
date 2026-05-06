# 主车推行收尾黄线判定与停车状态机计划

> 执行状态: In Progress
> 日期: 2026-05-07
> 执行方式: Subagent-Driven

## 目标

按最小改动完成两件事:

1. 主车视觉在推行阶段给出黄色边线收尾判定。
2. 主车与辅车在判定成立后完成停车与状态切换。

## 任务拆分

### 任务 1: 主车运行时与状态机先补齐搬运结束收尾

**负责人:** 子代理任务 1

**修改范围:**

- `src/config/params.py`
- `src/vision/master/state_machine.py`
- `src/vision/master/forward_runtime.py`
- `tests/unit/vision/test_master_state_machine.py`
- `tests/unit/runtime/test_master_forward_runtime.py`

**任务目标:**

- 先把主车在正式搬运阶段需要下发的通信语义补齐。
- 主车进入正式搬运后, 明确主车视觉收尾 hook 的上下文和辅车搬运态同步口径。
- 主车收到搬运结束事件后立即停车, 并显式向辅车下发停止态通信。
- 补齐状态机、运行时和开发文档回归。

**完成判据:**

- 主车正式搬运阶段的视觉 hook 入口已经明确。
- 主车搬运结束后会向辅车同步 `ASSISTANT_IDLE`。
- 原有寻找、绕行、搬运入口对正流程测试不回退。

### 任务 2: 主车视觉侧补齐搬运收尾 hook

**负责人:** 子代理任务 2

**修改范围:**

- `../SmartCar2026-Vision/master/main.py`
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**任务目标:**

- 按任务 1 已经定下来的主车搬运上下文接入新的收尾 hook。
- 新增主车推行收尾 hook 配置与参数。
- 实现“物体外扩一圈 -> 黄色占比 -> 连续稳定 -> 收尾事件”的最小判定。
- 保持现有主车视觉速度输出主线不变。
- 补齐视觉侧回归测试与说明。

**完成判据:**

- 主车视觉能在新 hook 下回报搬运结束事件。
- 原有寻找与搬运入口对正测试不回退。

### 任务 3: 文档同步, 等用户单独触发

**负责人:** 当前会话

**修改范围:**

- `docs/developer/state.md`
- `docs/developer/protocol.md`
- `docs/developer/vision.md`
- `../SmartCar2026-Vision/README.md`

**任务目标:**

- 在代码和测试稳定后, 同步主车搬运收尾的状态、协议和视觉职责事实。
- 本任务默认不执行, 只在用户在收尾阶段主动要求后执行。

## 执行顺序

1. 先做任务 1, 先把主车与辅车在搬运收尾阶段的通信和状态流转定住。
2. 再做任务 2, 让主车视觉按这个上下文补齐新的完成信号。
3. 两个实现任务都完成后, 统一跑主车仓库与视觉仓库测试。
4. 文档任务默认跳过, 等用户主动要求后再执行。

## 收口检查

- 检查改动是否仍是最小闭环。
- 检查是否只新增了必要参数与状态语义。
- 检查文档是否只描述当前事实。
- 检查 Spec / Plan 状态是否更新为 `Archive`。
