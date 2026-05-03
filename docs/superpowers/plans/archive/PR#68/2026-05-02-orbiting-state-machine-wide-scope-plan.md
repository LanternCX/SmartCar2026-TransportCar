# 主车寻找与绕行状态机实施计划

> 执行状态: Archive  
> 创建日期: 2026-05-02  
> 面向执行者: 使用 Subagent-Driven Development 逐任务执行；每个任务完成后由主流程 review，再进入下一任务。

**目标:** 实现主车 `IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE` 状态链路，并让辅车在主车绕行时进入 `IDLE`。

**架构:** 主车角色运行时拥有全局状态机；主车本车 `UART6` 负责视觉 hook 和视觉事件；`UART8` 负责主辅速度前馈与辅车状态同步；辅车角色运行时维护由主车同步驱动的子状态。

**技术栈:** RT1021 + MicroPython、主机侧 Python 3.8+、pytest、现有 `src/` 单根目录结构。

---

## 文件结构

### 新建

- `src/protocol/state.py`  
  维护状态编号、目标编号和事件编号常量，避免状态机和测试散落魔法数字。

- `src/vision/master/state_machine.py`  
  维护主车全局状态、视觉 hook 上下文、视觉事件判定、绕行进入和完成判定。

- `tests/unit/vision/test_master_state_machine.py`  
  覆盖主车状态机纯逻辑。

### 修改

- `src/config/params.py`  
  增加主车绕行绝对目标角度参数。

- `src/core/runtime.py`  
  提供主车角色层可调用的 rear only 绝对角度目标入口，并保持完成后零输出。

- `src/vision/master/forward_runtime.py`  
  装配主车状态机；处理 `UART6` 上的视觉 hook 确认、视觉事件确认、视觉速度输入和主辅状态同步。

- `src/vision/assistant/follow_runtime.py`  
  增加辅车子状态；`IDLE` 中保持串口读取和确认，但底盘输出零。

- `docs/developer/state.md`  
  同步状态流、状态编号、事件语义和跳转原则。

- `docs/developer/protocol.md`  
  同步主车本地视觉链路和主辅链路在本任务中的可靠语义。

- `docs/developer/control.md`  
  同步控制职责、绕行角度基准、rear only 使用边界。

- `docs/developer/vision.md`  
  同步视觉 hook 命中职责和辅车 idle 期间视觉修正边界。

- `tests/unit/runtime/test_master_forward_runtime.py`  
  覆盖主车角色运行时与串口行为。

- `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`  
  覆盖辅车 `IDLE` 下零输出和 `SEARCH_OBJECT` 下跟随行为。

- `tests/unit/core/test_runtime_public_api.py`  
  覆盖共享底盘 rear only 绝对角度目标入口。

- `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`  
  覆盖状态编号和主车视觉可靠包格式。

---

## Task 1: 状态常量与协议契约

**目标:** 建立正式状态、目标和事件常量，测试锁住编号与短包格式。

**Files:**
- Create: `src/protocol/state.py`
- Modify: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`

**步骤:**

- [ ] 编写协议契约测试，断言状态编号为 `IDLE=0`、`SEARCH_OBJECT=1`、`ORBITING=2`、`STOP=3`。
- [ ] 编写协议契约测试，断言目标编号包含 `NONE=0`、`OBJECT=1`。
- [ ] 编写协议契约测试，断言 `TARGET_FOUND=6` 可用于 `r,<reliable_seq>,<context_id>,<event>,<value>`。
- [ ] 运行契约测试，确认新增断言失败。
- [ ] 新建 `src/protocol/state.py`，只放常量和简短中文 Doxygen 注释。
- [ ] 运行契约测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/contract/serial_protocol/test_serial_packet_protocol_contract.py -q`

---

## Task 2: 主车状态机纯逻辑

**目标:** 用纯逻辑对象表达 `IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE`，不触碰硬件。

**Files:**
- Create: `src/vision/master/state_machine.py`
- Create: `tests/unit/vision/test_master_state_machine.py`

**步骤:**

- [ ] 编写测试：状态机初始为 `IDLE`，首次推进后进入 `SEARCH_OBJECT` 并创建 hook 上下文。
- [ ] 编写测试：`SEARCH_OBJECT` 下上下文匹配的 `TARGET_FOUND` 触发 `ORBITING`。
- [ ] 编写测试：上下文不匹配的合法事件不改变状态。
- [ ] 编写测试：重复 `TARGET_FOUND` 不重复触发绕行进入动作。
- [ ] 编写测试：`ORBITING` 完成后进入 `IDLE`。
- [ ] 编写测试：`ORBITING` 目标角度为上电基准航向 `+90°`。
- [ ] 运行测试，确认失败。
- [ ] 实现状态机对象，提供单拍推进、视觉事件输入、待发送 hook、待发送辅车状态和绕行命令输出。
- [ ] 运行测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/vision/test_master_state_machine.py -q`

---

## Task 3: 共享底盘 rear only 绝对角度入口

**目标:** 给主车状态机提供明确的底盘动作入口，避免角色层直接改共享底盘内部字段。

**Files:**
- Modify: `src/core/runtime.py`
- Modify: `tests/unit/core/test_runtime_public_api.py`

**步骤:**

- [ ] 编写测试：调用 rear only 绝对角度入口后，底盘进入角度锁定状态。
- [ ] 编写测试：入口启用 rear only 模式。
- [ ] 编写测试：入口写入的角度目标为调用方传入的绝对角度。
- [ ] 编写测试：角度到达并解锁后，rear only 模式关闭，底盘输出零。
- [ ] 运行测试，确认失败。
- [ ] 在 `TransportCar` 增加公开方法，封装 rear only 绝对角度目标写入。
- [ ] 保持现有速度入口行为不变。
- [ ] 运行相关单元测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/core/test_runtime_public_api.py -q`

---

## Task 4: 主车 `UART6` hook、事件确认与状态机装配

**目标:** 主车运行时在本车 `UART6` 上完成视觉 hook 发送、确认处理、事件确认和状态迁移。

**Files:**
- Modify: `src/vision/master/forward_runtime.py`
- Modify: `tests/unit/runtime/test_master_forward_runtime.py`

**步骤:**

- [ ] 编写测试：主车首次运行进入 `SEARCH_OBJECT` 后向 `UART6` 写出 hook 同步包。
- [ ] 编写测试：收到 `a,<reliable_seq>` 后停止重复发送对应 hook 包。
- [ ] 编写测试：收到上下文匹配的 `TARGET_FOUND` 后，主车调用 rear only 绝对角度入口。
- [ ] 编写测试：收到合法视觉 `r` 包后，主车总是向 `UART6` 写确认包。
- [ ] 编写测试：上下文不匹配的视觉 `r` 包只确认，不触发绕行。
- [ ] 编写测试：进入 `ORBITING` 后不再把主车视觉 `v` 搜索速度写入底盘。
- [ ] 编写测试：进入 `ORBITING` 后向 `UART8` 输出零前馈。
- [ ] 运行测试，确认失败。
- [ ] 将主车运行时的 `UART6` 解析切到正式 `protocol.packet` 边界。
- [ ] 装配主车状态机，按状态机输出执行 hook 发送、事件确认、底盘绕行命令和辅车同步。
- [ ] 保持 `UART3` 同拍优先级规则。
- [ ] 运行主车运行时测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`

---

## Task 5: 辅车子状态机与 `IDLE` 零输出

**目标:** 辅车由主车状态同步控制跟随或空闲，`IDLE` 中停止融合前馈和视觉修正。

**Files:**
- Modify: `src/vision/assistant/follow_runtime.py`
- Modify: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

**步骤:**

- [ ] 编写测试：辅车收到 `s,<seq>,0,0,0` 后确认并进入 `IDLE`。
- [ ] 编写测试：辅车 `IDLE` 中收到 `UART8` 前馈和 `UART6` 视觉修正时，底盘输出仍为零。
- [ ] 编写测试：辅车 `IDLE` 中继续读取串口并确认状态同步包。
- [ ] 编写测试：辅车收到 `SEARCH_OBJECT` 同步后恢复跟随融合规则。
- [ ] 运行测试，确认失败。
- [ ] 在辅车运行时中增加子状态字段和状态同步应用逻辑。
- [ ] 将速度融合入口加上子状态门控。
- [ ] 运行辅车运行时测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py -q`

---

## Task 6: 主辅状态同步联动

**目标:** 主车进入 `SEARCH_OBJECT` 时允许辅车跟随，进入 `ORBITING` 时让辅车 `IDLE`。

**Files:**
- Modify: `src/vision/master/forward_runtime.py`
- Modify: `tests/unit/runtime/test_master_forward_runtime.py`

**步骤:**

- [ ] 编写测试：主车进入 `SEARCH_OBJECT` 时通过 `UART8` 同步辅车进入 `SEARCH_OBJECT`。
- [ ] 编写测试：主车进入 `ORBITING` 时通过 `UART8` 同步辅车进入 `IDLE`。
- [ ] 编写测试：辅车状态同步在收到确认前重复发送，确认后停止重复发送。
- [ ] 运行测试，确认失败。
- [ ] 将主车状态机输出的辅车状态同步接入现有 `UART8` 同步发送机制。
- [ ] 保持速度前馈和状态同步包分开发送。
- [ ] 运行主车运行时测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`

---

## Task 7: 开发文档同步

**目标:** 让协议、状态、控制和视觉文档与实现语义一致。

**Files:**
- Modify: `docs/developer/state.md`
- Modify: `docs/developer/protocol.md`
- Modify: `docs/developer/control.md`
- Modify: `docs/developer/vision.md`

**步骤:**

- [ ] 更新状态机文档，写明 `IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE`。
- [ ] 更新状态编号表，收口为本任务最小状态集合。
- [ ] 更新 `ORBITING` 语义，写明 rear only 和上电基准航向 `+90°`。
- [ ] 更新协议文档，写明主车 `UART6` hook 和事件可靠确认语义。
- [ ] 更新协议文档，写明主车 `UART8` 对辅车 `IDLE` 的同步语义。
- [ ] 更新控制文档，写明主车状态所有权和绕行动作边界。
- [ ] 更新视觉文档，写明视觉只回报 hook 命中，辅车 `IDLE` 中视觉修正不生效。
- [ ] 自查文档不使用历史性口吻。

**验证方式:**

- 人工 review 文档语义。
- `grep -R "OBJECT_FOUND\|LOCK_OBJECT\|MASTER_ALIGN_OBJECT\|ASSISTANT_ALIGN_OBJECT\|TRACK_OBJECT\|WAIT_PEER" docs/developer src tests` 确认无本任务不需要的正式状态残留。

---

## Task 8: 集成验证与收口 review

**目标:** 确认主机侧行为、协议契约和文档规则全部通过。

**Files:**
- Review only

**步骤:**

- [ ] 运行主机侧单元测试。
- [ ] 运行主机侧契约测试。
- [ ] 运行联合测试。
- [ ] 检查主车状态机无模块级可变运行时全局状态。
- [ ] 检查主车状态机没有阻塞等待确认。
- [ ] 检查新增注释为中文 Doxygen 风格。
- [ ] 检查文档只描述当前事实。
- [ ] 整理需要板端确认的检查项：hook 包发送、视觉事件确认、辅车 idle、rear only 绕行角度到达。

**验证命令:**

- `python3 -m pytest tests/unit -q`
- `python3 -m pytest tests/contract -q`
- `python3 -m pytest tests/unit tests/contract -q`

---

## 执行备注

- 每个任务只修改列出的文件，避免扩大改动面。
- 不执行 git commit，commit 消息在需要提交前向用户确认。
- 板端验证需要在主机测试通过后进行，确认串口链路、视觉事件、辅车停止和绕行动作实测结果。
