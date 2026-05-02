# 单车视觉 Hook 与绕行状态机实施计划

> 执行状态: Active  
> 创建日期: 2026-05-02  
> 面向执行者: 按任务顺序执行；每个任务完成后 review，再进入下一任务。

**目标:** 实现主车单车 `IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE` 链路。

**架构:** 主车角色运行时拥有状态机；主车本车 `UART6` 负责视觉 hook、视觉确认、视觉事件和视觉速度；共享底盘已有 rear only 模式，本计划只补主车状态机调用边界。

**技术栈:** RT1021 + MicroPython、主机侧 Python 3.8+、pytest、现有 `src/` 单根目录结构。

---

## 文件结构

### 新建

- `src/protocol/state.py`  
  维护状态编号、目标编号和事件编号常量。

- `src/vision/master/state_machine.py`  
  维护主车单车状态、视觉 hook 上下文、视觉事件判定、绕行进入和完成判定。

- `tests/unit/vision/test_master_state_machine.py`  
  覆盖主车状态机纯逻辑。

### 修改

- `src/config/params.py`  
  增加主车绕行绝对目标角度参数。

- `src/core/runtime.py`  
  复用现有 rear only 模式，补充主车角色层可调用的绝对角度目标入口。

- `src/vision/master/forward_runtime.py`  
  装配主车状态机；处理 `UART6` 上的视觉 hook 确认、视觉事件确认、视觉速度输入和绕行命令。

- `tests/unit/runtime/test_master_forward_runtime.py`  
  覆盖主车角色运行时与 `UART6` 行为。

- `tests/unit/core/test_runtime_public_api.py`  
  覆盖共享底盘 rear only 绝对角度目标入口。

- `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`  
  覆盖状态编号和主车视觉可靠包格式。

---

## Task 1: 状态常量与协议契约

**目标:** 建立正式状态、目标和事件常量，锁定单车链路编号。

**Files:**
- Create: `src/protocol/state.py`
- Modify: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`

**步骤:**

- [ ] 编写协议契约测试，断言 `IDLE=0`、`SEARCH_OBJECT=1`、`ORBITING=2`、`STOP=3`。
- [ ] 编写协议契约测试，断言 `NONE=0`、`OBJECT=1`。
- [ ] 编写协议契约测试，断言 `TARGET_FOUND=6` 可用于主车视觉事件回报包。
- [ ] 运行契约测试，确认新增断言失败。
- [ ] 新建 `src/protocol/state.py`，只放常量和必要中文 Doxygen 注释。
- [ ] 运行契约测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/contract/serial_protocol/test_serial_packet_protocol_contract.py -q`

---

## Task 2: 主车状态机纯逻辑

**目标:** 用纯逻辑对象表达 `IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE`。

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
- [ ] 实现状态机对象，提供单拍推进、视觉事件输入、待发送 hook 和绕行命令输出。
- [ ] 运行测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/vision/test_master_state_machine.py -q`

---

## Task 3: 复用现有 rear only 的绝对角度入口

**目标:** 复用共享底盘现有 rear only 模式，给主车状态机提供明确底盘动作入口，避免角色层直接改共享底盘内部字段。

**Files:**
- Modify: `src/core/runtime.py`
- Modify: `tests/unit/core/test_runtime_public_api.py`
- Modify: `src/config/params.py`

**步骤:**

- [ ] 编写测试：调用 rear only 绝对角度入口后，底盘进入角度锁定状态。
- [ ] 编写测试：入口启用 rear only 模式。
- [ ] 编写测试：入口写入调用方传入的绝对角度目标。
- [ ] 编写测试：角度到达并解锁后，rear only 模式关闭，底盘输出零。
- [ ] 运行测试，确认失败。
- [ ] 在 `params.py` 增加 `MASTER_ORBIT_TARGET_DEG = 90`。
- [ ] 在 `TransportCar` 增加公开方法，封装现有 rear only 模式与绝对角度目标写入。
- [ ] 保持现有速度入口行为不变。
- [ ] 运行相关单元测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/core/test_runtime_public_api.py -q`

---

## Task 4: 主车 `UART6` hook、事件确认与绕行装配

**目标:** 主车运行时在本车 `UART6` 上完成视觉 hook 发送、确认处理、事件确认和绕行触发。

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
- [ ] 编写测试：绕行完成后主车进入 `IDLE` 并输出零量。
- [ ] 运行测试，确认失败。
- [ ] 将主车运行时的 `UART6` 解析切到正式 `protocol.packet` 边界。
- [ ] 装配主车状态机，按状态机输出执行 hook 发送、事件确认和底盘绕行命令。
- [ ] 保持 `UART3` 同拍优先级规则。
- [ ] 运行主车运行时测试，确认通过。

**验证命令:**

- `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`

---

## Task 5: 集成验证与收口 review

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
- [ ] 整理板端确认项：hook 包发送、视觉事件确认、rear only 绕行角度到达。

**验证命令:**

- `python3 -m pytest tests/unit -q`
- `python3 -m pytest tests/contract -q`
- `python3 -m pytest tests/unit tests/contract -q`

---

## 执行备注

- 本轮不修改辅车运行时。
- 本轮不新增主车到辅车的状态同步行为。
- 本轮不做开发文档同步，等单车链路调通后再单独处理。
- 不执行 git commit，commit 消息在需要提交前向用户确认。
- 板端验证需要在主机测试通过后进行。
