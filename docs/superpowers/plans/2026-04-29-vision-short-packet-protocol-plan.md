# OpenART 视觉短包协议对齐实施计划

## 执行状态

- 状态: Archive
- 创建日期: 2026-04-29
- 规格来源: `docs/superpowers/specs/2026-04-29-vision-short-packet-protocol-spec.md`
- 执行目标仓库: `../SmartCar2026-Vision`
- 执行方式: TDD + Subagent Driven Development
- 执行结果: 已完成

## 目标

将视觉仓库的 OpenART 到 RT1021 视觉主链路收口为车端已采用的短包协议 `v,<vx>,<vy>`, 同时保持视觉识别、阶段判断、控制量计算和逐帧发送行为不变。

## 架构约束

1. 视觉仓库保持 `main.py` 单文件运行时架构。
2. 运行时只改协议表达, 不调整硬件连接、串口编号、波特率、目标检测规则或控制参数。
3. 测试先行, 先确认旧协议测试失败, 再改实现。
4. 文档与注释只做规则检查, 不为文档文字单独写测试。
5. 不保留 `key=value` 视觉载荷兼容层。
6. 不执行提交, 除非用户另行确认 commit message。

## 文件边界

### 当前仓库

- 修改: `docs/superpowers/specs/2026-04-29-vision-short-packet-protocol-spec.md`
- 修改: `docs/superpowers/plans/2026-04-29-vision-short-packet-protocol-plan.md`

### 视觉仓库

- 修改: `tests/unit/test_vision_protocol_rebuild.py`
- 修改: `tests/contract/test_main_vision_protocol_contract.py`
- 修改: `main.py`
- 修改: `README.md`
- 修改: `docs/Protocol.md`

## Task 1: 测试先行锁定短包协议

**目标:** 让测试先表达正式视觉协议 `v,<vx>,<vy>`, 并确认当前实现因仍输出等号载荷而失败。

**文件:**

- 修改: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- 修改: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**步骤:**

1. 将 `format_vision_frame()` 的单元测试期望改为 `v,<vx>,<vy>`。
2. 将零量测试期望改为 `v,0,0`。
3. 增加或调整测试, 明确载荷不能包含 `=`、`vx=`、`vy=`、`dx=`、`dy=`、`lock=`。
4. 保留 `format_vision_frame()` 只接收两个输入的契约。
5. 保留 `build_follow_command()` 行为测试, 确认同一误差输入对应的 `command_vx` 和 `command_vy` 数值不变。
6. 运行 `python3 -m pytest tests/unit/test_vision_protocol_rebuild.py tests/contract/test_main_vision_protocol_contract.py -q`。
7. 期望结果: 测试失败, 失败点集中在输出仍为等号载荷。

**Review 点:**

- 测试只约束行为和协议输出, 不通过源码字符串强行约束实现细节。
- 不删除控制行为测试。

## Task 2: 实现视觉运行时短包输出

**目标:** 将运行时正式输出改为 `v,<vx>,<vy>`, 不改变控制行为。

**文件:**

- 修改: `../SmartCar2026-Vision/main.py`
- 验证: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`

**步骤:**

1. 更新文件说明、函数说明和附近注释, 使用当前短包协议事实描述。
2. 将 `format_vision_frame()` 输出格式改为 `v,<vx>,<vy>`。
3. 保持数值格式化规则: 接近零输出 `0`, 去除无意义尾零, 保留符号。
4. 保持函数输入仍为 `vx` 和 `vy` 两个速度修正量。
5. 保持主循环逐帧调用 `write_line()` 的方式不变。
6. 保持无目标和保持区输出零量。
7. 运行 `python3 -m pytest tests/unit/test_vision_protocol_rebuild.py tests/contract/test_main_vision_protocol_contract.py -q`。
8. 期望结果: 运行时协议相关测试通过; 若文档契约仍失败, 进入 Task 3。

**Review 点:**

- `main.py` 仍是唯一运行时入口。
- 没有新增兼容分支。
- 没有新增 `omega`。
- 没有修改控制参数和目标检测逻辑。

## Task 3: 同步视觉仓库文档口径

**目标:** 让视觉仓库说明文档只描述短包协议和当前职责边界。

**文件:**

- 修改: `../SmartCar2026-Vision/README.md`
- 修改: `../SmartCar2026-Vision/docs/Protocol.md`

**步骤:**

1. 将 README 中的通信说明改为 OpenART 通过 `UART(2)` 向 RT1021 `UART6` 发送 `v,<vx>,<vy>`。
2. 将 README 中无目标和保持区说明改为发送 `v,0,0`。
3. 将 `docs/Protocol.md` 改为视觉短包协议说明。
4. 明确 `UART6` 视觉链路不发送 `omega`。
5. 明确高频视觉数据流不逐帧确认, 接收端消费最近一帧。
6. 清理文档中的等号载荷、位置命令和非主线字段表述。
7. 使用文本搜索和人工 Review 检查文档口径。

**Review 点:**

- 文档使用中文。
- 文档不使用历史性口吻。
- 文档不解释兼容层。

## Task 4: 全量回归与残留检查

**目标:** 确认协议链路和仓库文字口径完成收口。

**文件:**

- 验证: `../SmartCar2026-Vision/main.py`
- 验证: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- 验证: `../SmartCar2026-Vision/README.md`
- 验证: `../SmartCar2026-Vision/docs/Protocol.md`

**步骤:**

1. 运行 `python3 -m pytest tests/unit tests/contract -q`。
2. 搜索正式文件中是否还有视觉等号载荷样例。
3. 搜索正式文档和运行时注释中是否还有位置命令、`lock=`、`dx=`、`dy=` 等非当前协议口径。
4. 搜索正式运行路径是否存在 `omega` 输出。
5. 检查注释与文档是否为当前事实描述。
6. 拉取 subagent review, 重点检查协议残留、行为一致性和文档口径。
7. 根据 review 结果修正问题并重新运行回归。

**Review 点:**

- 无目标、保持区、单轴、双轴行为都被测试覆盖。
- 协议迁移不影响视觉控制数值。
- 文档和注释没有历史性口吻。

## Task 5: 收口当前仓库 spec 和 plan 状态

**目标:** 将已经执行的规格与计划标记为 Archive, 保持后续改动需要新建规格或计划。

**文件:**

- 修改: `docs/superpowers/specs/2026-04-29-vision-short-packet-protocol-spec.md`
- 修改: `docs/superpowers/plans/2026-04-29-vision-short-packet-protocol-plan.md`

**步骤:**

1. 确认视觉仓库验证已通过。
2. 将 spec 执行状态改为 `Archive`。
3. 将 plan 执行状态改为 `Archive`。
4. 在最终汇报中说明未执行 commit。

**Review 点:**

- 不归档未完成事项。
- 不在当前仓库写入视觉实现细节以外的额外说明。

## 最终验证命令

在 `../SmartCar2026-Vision` 执行:

1. `python3 -m pytest tests/unit/test_vision_protocol_rebuild.py tests/contract/test_main_vision_protocol_contract.py -q`
2. `python3 -m pytest tests/unit tests/contract -q`

## 完成标准

1. 视觉端正式输出为 `v,<vx>,<vy>`。
2. `UART6` 视觉链路不发送 `omega`。
3. 无目标和保持区输出 `v,0,0`。
4. 同一误差输入对应的 `command_vx` 和 `command_vy` 数值保持不变。
5. 视觉仓库正式文档与测试口径一致。
6. 所有主机侧 unit 和 contract 测试通过。
7. 当前仓库 spec 和 plan 状态为 `Archive`。
