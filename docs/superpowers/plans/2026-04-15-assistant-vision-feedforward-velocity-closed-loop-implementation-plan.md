# 辅车视觉层速度前馈与本地视觉闭环 Implementation Plan

> 状态: Archive
> **给 Agent 工作者:** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现。步骤统一使用复选框 `- [ ]` 维护执行状态。
> 当前约束以 `docs/developer/control.md`、`docs/developer/vision.md` 与 `.agents/skills/using-rules/references/strategy-and-control.md` 为准。

**Goal:** 在不改 `TransportCar` 与 `services/` 共享内核、也不改现有主辅通信协议的前提下, 让 `src/vision/assistant/` 正式接管辅车本地视觉与 `UART3` 上现有控制协议中的速度控制量, 在角色层完成速度融合并把结果接入辅车现有速度执行主链。

**Architecture:** 继续保留当前 `remote_control.py -> vision/assistant/runtime.py` 的启动路径, 但把 `vision/assistant/` 从空装配壳提升为真实角色层。具体做法是在 `vision/assistant/` 内增加一个基于共享底盘的辅车角色运行时, 由它真正进入控制周期并参与串口读取编排, 优先消费 `UART6` 上的现有视觉协议和 `UART3` 上的现有控制协议速度控制包、维护最小状态、输出统一的 `vx / vy / omega` 速度目标, 并通过当前已有速度接口和内核通信。

**Tech Stack:** Python, MicroPython 兼容运行时代码, pytest unit tests, 当前 `src/vision/` 角色包结构, 当前 `UART3` / `UART6` 字符串链路

---

## 文件结构与职责

- Create: `src/vision/assistant/follow_runtime.py`
  负责辅车角色运行时主体, 基于共享底盘建立辅车角色层, 进入控制周期、接管串口读取编排、推进状态并提交融合后的速度目标。

- Create: `src/vision/assistant/control_protocol_input.py`
  负责解析 `UART3` 上现有控制协议中的速度控制包, 维护最近一次有效控制量与超时判断。

- Create: `src/vision/assistant/vision_input.py`
  负责接入辅车本地视觉输入, 复用当前 `x=<x>,y=<y>` 解析语义并维护有效期。

- Create: `src/vision/assistant/velocity_fusion.py`
  负责把现有控制协议中的速度控制量与本地视觉纠偏统一为辅车最终速度目标, 同时产出最小状态。

- Create: `src/vision/assistant/diagnostics.py`
  负责组织辅车角色层调试观测, 让联调时能看到控制协议速度量、视觉、状态和融合输出。

- Modify: `src/vision/assistant/runtime.py`
  从“直接创建共享底盘”改成“创建辅车角色运行时”。

- Modify: `src/vision/assistant/__init__.py`
  保持对外入口不变, 继续从包入口暴露 `create_transport_car`。

- Modify: `tests/unit/test_role_vision_layer_factory.py`
  把辅车运行入口的既有断言收口到“创建辅车角色运行时”, 主车入口断言继续保持共享底盘方向。

- Create: `tests/unit/test_assistant_control_protocol_input.py`
  锁定 `UART3` 上现有控制协议速度控制包的解析、缓存和超时语义。

- Create: `tests/unit/test_assistant_vision_input.py`
  锁定辅车本地视觉输入的解析、缓存和超时语义。

- Create: `tests/unit/test_assistant_velocity_fusion.py`
  锁定“控制协议速度量给节奏, 视觉做纠偏”的速度融合和最小状态语义。

- Create: `tests/unit/test_assistant_follow_runtime.py`
  锁定辅车角色运行时对 `UART3` / `UART6` 的接管、普通命令透传、融合输出写回与诊断快照。

- Modify: `docs/developer/vision.md`
  同步正式文档口径, 写清楚辅车角色层负责接入本地视觉与 `UART3` 上现有控制协议速度控制包。

- Modify: `docs/developer/control.md`
  同步正式控制文档口径, 写清楚这条辅车最小闭环当前走速度式角色层入口, 不把它继续写成位置式主线。

- Modify: `.agents/skills/using-rules/references/strategy-and-control.md`
  收口实现阶段规则, 避免后续实现仍被“当前跟随主线只能位置式”这类旧口径带偏。

## Task 1: 收口辅车角色运行入口

**Files:**
- Create: `src/vision/assistant/follow_runtime.py`
- Modify: `src/vision/assistant/runtime.py`
- Modify: `src/vision/assistant/__init__.py`
- Modify: `tests/unit/test_role_vision_layer_factory.py`
- Create: `tests/unit/test_assistant_follow_runtime.py`

- [ ] **Step 1: 先把入口测试改成“辅车运行入口创建角色运行时”**

在 `tests/unit/test_role_vision_layer_factory.py` 里保留主车入口断言不变, 只把辅车入口断言改成以下口径:

1. `vision.assistant.runtime.create_transport_car()` 不再直接回到裸共享底盘实例。
2. 辅车入口创建的是辅车角色运行时对象。
3. `vision/__init__.py` 的角色分流关系保持不变。

- [ ] **Step 2: 新增辅车角色运行时最小失败测试**

在 `tests/unit/test_assistant_follow_runtime.py` 中新增最小失败用例, 锁定以下行为:

1. 辅车角色运行时基于共享底盘构建, 但对外仍保留 `wheel_states`、`imu`、`mark_tick()`、`set_ticker()` 和 `step()` 这些现有启动壳会用到的外观。
2. `remote_control.py` 不需要修改就能继续创建辅车运行对象。
3. 主车运行入口继续保持共享底盘当前行为, 这次只改辅车。
4. 辅车角色运行时的 `step()` 不是简单转发占位, 而是后续接入串口读取和角色层控制周期编排的正式边界。

- [ ] **Step 3: 运行测试确认当前失败**

运行:

`python3 -m pytest tests/unit/test_role_vision_layer_factory.py tests/unit/test_assistant_follow_runtime.py -q`

预期:

1. 新增的辅车运行时断言失败。
2. 失败原因集中在辅车角色运行时还不存在或入口仍直接返回裸共享底盘。

- [ ] **Step 4: 实现辅车角色运行时最小骨架**

在 `src/vision/assistant/follow_runtime.py` 中建立辅车角色运行时主体, 明确采用“基于共享底盘的辅车角色层”方案。这里先只完成最小骨架:

1. 共享底盘实例的创建。
2. 角色层对象的对外外观转发。
3. `runtime.py` 改为创建这个角色层对象。
4. `step()` 被明确立成角色层控制周期编排入口, 后续串口接管和融合刷新都从这里进入。

注意:

1. 这一轮先不要接入真正的控制协议输入和视觉融合。
2. 先把运行入口边界立起来, 避免后续协议和融合逻辑重新堆回 `runtime.py`。

- [ ] **Step 5: 重新运行入口相关测试确认通过**

运行:

`python3 -m pytest tests/unit/test_role_vision_layer_factory.py tests/unit/test_assistant_follow_runtime.py tests/unit/test_remote_control_role_dispatch.py -q`

预期:

1. 角色分流测试全绿。
2. 辅车运行入口已切到角色运行时。
3. `remote_control.py` 启动壳断言继续保持通过。

- [ ] **Step 6: 提交检查点**

如需提交, 先向用户确认提交消息, 不直接提交。

## Task 2: 建立 `UART3` 控制协议速度控制包输入层

**Files:**
- Create: `src/vision/assistant/control_protocol_input.py`
- Create: `tests/unit/test_assistant_control_protocol_input.py`

- [ ] **Step 1: 写控制协议输入失败测试**

在 `tests/unit/test_assistant_control_protocol_input.py` 中锁定以下行为:

1. 只消费 `UART3` 上现有控制协议中的速度控制包, 至少包含 `vx / vy / omega` 语义。
2. 普通查询和非速度控制命令不能被当成控制协议速度量误吞。
3. 合法速度控制包会刷新最近一次有效控制量缓存。
4. 超过有效期后, 控制量缓存自动失效。
5. 非法字段、重复字段和越界值不会产生有效控制量。

- [ ] **Step 2: 运行控制协议输入测试确认失败**

运行:

`python3 -m pytest tests/unit/test_assistant_control_protocol_input.py -q`

预期:

失败原因集中在输入适配类尚不存在或控制量缓存语义尚未建立。

- [ ] **Step 3: 实现最小控制协议输入层**

在 `src/vision/assistant/control_protocol_input.py` 中实现以下内容:

1. 解析现有控制协议中的速度控制包。
2. 保存最近一次有效 `vx / vy / omega`。
3. 提供读取当前有效控制量和判断超时的方法。
4. 提供只读快照, 供后续诊断输出使用。

这里要坚持两条边界:

1. 这层只负责“识别并保存控制协议速度量”, 不负责融合。
2. 这层不能直接把控制量写进共享底盘的 `last_cmd`。

- [ ] **Step 4: 重新运行控制协议输入测试确认通过**

运行:

`python3 -m pytest tests/unit/test_assistant_control_protocol_input.py -q`

预期:

控制协议速度控制包识别、缓存、超时清理和非法输入拒绝全部通过。

- [ ] **Step 5: 提交检查点**

如需提交, 先向用户确认提交消息, 不直接提交。

## Task 3: 建立辅车本地视觉输入适配层

**Files:**
- Create: `src/vision/assistant/vision_input.py`
- Create: `tests/unit/test_assistant_vision_input.py`

- [ ] **Step 1: 写本地视觉输入失败测试**

在 `tests/unit/test_assistant_vision_input.py` 中锁定以下行为:

1. 只消费 `UART6` 上的 `x=<x>,y=<y>` 输入。
2. 合法输入会刷新最近一次视觉观测缓存。
3. 超时后视觉观测会失效。
4. 非法输入不会污染最近一次有效观测。
5. 这层只输出观测和年龄, 不直接生成底盘控制命令。

- [ ] **Step 2: 运行本地视觉输入测试确认失败**

运行:

`python3 -m pytest tests/unit/test_assistant_vision_input.py -q`

预期:

失败原因集中在本地视觉输入适配层尚不存在。

- [ ] **Step 3: 实现本地视觉输入适配层**

在 `src/vision/assistant/vision_input.py` 中实现最小适配层。这里推荐复用现有的 `services.vision_protocol.VisionProtocol` 解析规则, 但要把消费边界留在 `vision/assistant`:

1. 角色层负责决定哪些输入由本地视觉消费。
2. 共享解析器只作为现成的 `x=<x>,y=<y>` 解析工具使用。
3. 视觉输入适配层负责输出当前观测、有效期和最小只读快照。

- [ ] **Step 4: 重新运行本地视觉输入测试确认通过**

运行:

`python3 -m pytest tests/unit/test_assistant_vision_input.py -q`

预期:

合法输入、超时、非法输入和来源过滤全部通过。

- [ ] **Step 5: 提交检查点**

如需提交, 先向用户确认提交消息, 不直接提交。

## Task 4: 建立速度融合与最小状态机理

**Files:**
- Create: `src/vision/assistant/velocity_fusion.py`
- Create: `tests/unit/test_assistant_velocity_fusion.py`

- [ ] **Step 1: 写速度融合失败测试**

在 `tests/unit/test_assistant_velocity_fusion.py` 中锁定以下行为:

1. 视觉有效且 `UART3` 上的控制协议速度量有效时, 输出 `tracking` 状态和融合后的 `vx / vy / omega`。
2. 控制协议速度量失效但视觉有效时, 输出 `vision_only` 状态并收紧速度上限。
3. 视觉失效时, 输出 `fault_stop` 状态和零速度。
4. 两路输入都无效时, 输出 `idle` 或 `fault_stop` 的零速度语义, 不允许继续沿用上一拍速度盲跑。
5. 本地视觉不生成外部角度目标, `omega` 由 `UART3` 上的控制协议速度量或本地方向保持语义兜住。

- [ ] **Step 2: 运行速度融合测试确认失败**

运行:

`python3 -m pytest tests/unit/test_assistant_velocity_fusion.py -q`

预期:

失败原因集中在融合器和最小状态语义尚不存在。

- [ ] **Step 3: 实现融合器与最小状态**

在 `src/vision/assistant/velocity_fusion.py` 中实现以下内容:

1. 统一的融合输出结构, 至少包含 `state`、`vx`、`vy`、`omega`。
2. `idle / tracking / vision_only / fault_stop` 四个最小状态。
3. “控制协议速度量给节奏, 视觉做纠偏”的融合规则。
4. 统一限幅与降级限幅规则。

这里要注意:

1. 这层只负责“从输入到统一速度输出”。
2. 不在这里引入比赛级大状态机和更高层任务语义。

- [ ] **Step 4: 重新运行速度融合测试确认通过**

运行:

`python3 -m pytest tests/unit/test_assistant_velocity_fusion.py -q`

预期:

融合状态、零速度收口和降级语义全部通过。

- [ ] **Step 5: 提交检查点**

如需提交, 先向用户确认提交消息, 不直接提交。

## Task 5: 在辅车角色运行时内接管串口读取、接入控制周期并写回统一速度目标

**Files:**
- Modify: `src/vision/assistant/follow_runtime.py`
- Create: `src/vision/assistant/diagnostics.py`
- Modify: `tests/unit/test_assistant_follow_runtime.py`

- [ ] **Step 1: 补齐辅车角色运行时失败测试**

在 `tests/unit/test_assistant_follow_runtime.py` 中补齐以下断言:

1. `UART3` 上现有控制协议中的速度控制包由辅车角色层优先消费, 不直接落到共享底盘普通命令入口。
2. `UART6` 上供本地视觉闭环使用的数据由辅车角色层优先消费, 不再触发共享底盘原有默认视觉链。
3. 普通查询和非速度控制命令仍能透传给共享底盘当前入口。
4. 辅车角色运行时会在 `step()` 控制周期里完成“读取输入 -> 刷新融合 -> 写回速度目标”的整段编排, 而不是把角色层逻辑挂在循环外面。
5. 每次更新后, 辅车角色层会把融合后的 `vx / vy / omega` 写回共享底盘当前速度目标入口。
6. 角色层诊断快照能够看到当前状态、输入年龄和融合输出。

- [ ] **Step 2: 运行角色运行时集成测试确认失败**

运行:

`python3 -m pytest tests/unit/test_assistant_follow_runtime.py -q`

预期:

失败原因集中在角色层尚未真正接管 `UART3` / `UART6` 或尚未写回统一速度目标。

- [ ] **Step 3: 实现角色层输入接管与统一写回**

在 `src/vision/assistant/follow_runtime.py` 中完成以下集成:

1. 优先拦截 `UART3` 上现有控制协议中的速度控制包。
2. 优先拦截 `UART6` 本地视觉输入。
3. 非速度控制命令和普通查询继续透传给共享底盘。
4. 禁用共享底盘内部原有那条默认视觉位置目标刷新链, 避免两套控制并行。
5. 在角色层 `step()` 控制周期里读取“控制协议输入层 + 本地视觉输入 + 融合器”结果, 统一写回共享底盘速度目标。
6. 角色层的串口接管必须发生在共享底盘默认消费之前, 这样本地视觉与 `UART3` 速度控制包才不会先被内核错误消费。

这一轮要坚持两条硬边界:

1. 不修改 `TransportCar` 源码。
2. 共享底盘只看到已经融合好的速度目标, 不再分别接收视觉和控制协议速度量。
3. 辅车角色运行时必须真正参与整段循环, 不能退化为只在 `create_transport_car()` 里返回对象的静态壳。

- [ ] **Step 4: 加入角色层诊断输出**

在 `src/vision/assistant/diagnostics.py` 中组织最小观测, 并在辅车角色运行时里接入。至少包含:

1. 当前最小状态。
2. 控制协议速度量年龄。
3. 视觉年龄。
4. 当前控制协议速度量贡献。
5. 当前视觉贡献。
6. 当前融合输出。

- [ ] **Step 5: 重新运行角色运行时测试确认通过**

运行:

`python3 -m pytest tests/unit/test_assistant_follow_runtime.py tests/unit/test_remote_control_role_dispatch.py -q`

预期:

1. 角色层成功接管辅车输入。
2. 默认启动壳继续可用。
3. 辅车角色运行时已经能统一输出速度目标。

- [ ] **Step 6: 提交检查点**

如需提交, 先向用户确认提交消息, 不直接提交。

## Task 6: 同步正式文档与实现规则, 完成总验证

**Files:**
- Modify: `docs/developer/vision.md`
- Modify: `docs/developer/control.md`
- Modify: `.agents/skills/using-rules/references/strategy-and-control.md`

- [ ] **Step 1: 同步正式视觉文档**

更新 `docs/developer/vision.md`, 明确以下事实:

1. `vision/assistant` 是辅车本地视觉闭环和 `UART3` 上现有控制协议速度控制量的正式角色层入口。
2. 辅车角色层负责本地视觉输入和主车转发来的当前速度控制量的本地融合。
3. 本轮不把这条辅车闭环继续写成主车统一闭环。

- [ ] **Step 2: 同步正式控制文档**

更新 `docs/developer/control.md`, 明确以下事实:

1. 当前这条辅车最小闭环通过角色层速度目标接入共享底盘执行链。
2. 这次实现不修改共享控制内核。
3. 这条最小闭环当前按速度式角色层入口理解, 不再继续引用和它冲突的旧位置式口径。

- [ ] **Step 3: 同步实现规则入口**

更新 `.agents/skills/using-rules/references/strategy-and-control.md`, 把当前实现阶段的规则收口为:

1. 辅车角色层可在不改共享底盘的前提下接管速度式最小闭环。
2. `vision/assistant` 是这条辅车闭环的正式接入层。
3. 后续实现不再被和当前 spec 冲突的旧跟随口径带偏。

- [ ] **Step 4: 运行主机侧总验证**

运行:

`python3 -m pytest tests/unit/test_role_vision_layer_factory.py tests/unit/test_remote_control_role_dispatch.py tests/unit/test_assistant_control_protocol_input.py tests/unit/test_assistant_vision_input.py tests/unit/test_assistant_velocity_fusion.py tests/unit/test_assistant_follow_runtime.py -q`

预期:

所有和辅车角色闭环直接相关的主机侧测试全绿。

- [ ] **Step 5: 整理板端联调确认清单**

在实现收口时通过对话记录以下最小板端确认项:

1. 辅车角色正常进入 `vision/assistant/` 运行链。
2. `UART3` 上主车转发的当前速度控制量正常时, 辅车能明显跟上主车节奏。
3. `UART3` 速度控制量临时断开时, 辅车会降级为保守视觉单撑模式。
4. 本地视觉断开时, 辅车立即停下。

- [ ] **Step 6: 提交检查点**

如需提交, 先向用户确认提交消息, 不直接提交。

## 计划自检

- Spec coverage: 本计划覆盖了 spec 的核心要求: 只在 `vision/assistant` 接入、保持共享内核不改、现有控制协议和本地视觉统一融合、最小状态与失效收口、诊断观测、正式文档和规则同步。
- Placeholder scan: 计划没有使用 `TBD`、`TODO`、后续补充或“类似 Task N”这类占位表述; 每个任务都给出了明确文件、测试入口和验证命令。
- Type consistency: 计划中的关键命名统一为 `control_protocol_input`、`vision_input`、`velocity_fusion`、`follow_runtime`、`diagnostics` 以及 `idle / tracking / vision_only / fault_stop`; `follow_runtime.step()` 被统一视为角色层控制周期与串口读取编排入口, 后续实现时不得改成循环外的旁路刷新模型。
