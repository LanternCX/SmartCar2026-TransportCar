# 主辅运行时结构清晰化重构实施计划

> **给执行代理的要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划，步骤使用复选框 `- [ ]` 跟踪。

**目标：** 让主辅运行时代码的常量、状态、控制、运行时和状态机边界重新清楚, 删除会误导静态分析和维护者的重复结构壳, 同时保持现有业务行为不退化。

**架构：** 先把 review 已确认的坏边界写成失败测试, 再按“参数边界 -> 重复壳文件 -> 入口收薄 -> 状态收口 -> 状态机边界 -> 目录职责收口 -> 注释与回归”的顺序重构。每个任务都只处理一类边界问题, 不把结构清理和功能扩展混做一件事。

**技术栈：** Python 3.8+、MicroPython 兼容代码、pytest、主辅双包板端入口、LSP / Pylance 友好导入语义。

---

## 文件结构与职责

- Modify: `src/master/config.py`
  明确主车硬件真值和板级事实边界。
- Modify: `src/assistant/config.py`
  明确辅车硬件真值和板级事实边界。
- Modify: `src/master/runtime_params.py`
  明确主车运行参数边界, 不混入硬件事实。
- Modify: `src/assistant/runtime_params.py`
  明确辅车运行参数边界, 不混入硬件事实。
- Delete: `src/master/decision.py`
  删除与 `master.vision.decision` 重复的外层壳文件。
- Delete: `src/master/vision_ingress.py`
  删除与 `master.vision.ingress` 重复的外层壳文件。
- Delete: `src/master/vision_state_machine.py`
  删除与 `master.vision.state_machine` 重复的外层壳文件。
- Modify: `src/master/status.py`
  先核对是否仍承担真实状态文本职责; 若主链、协议输出或日志仍直接依赖这里的非转手实现, 则保留并补职责注释; 若这里只剩转手导出, 再连同调用点与测试一起删除。
- Modify: `src/master/main.py`
  收薄主车入口, 只保留板端根目录直烧所需的最小逻辑。
- Modify: `src/assistant/main.py`
  收薄辅车入口, 只保留板端根目录直烧所需的最小逻辑。
- Create if needed: `src/assistant/state/*`
  若跨周期状态确有独立职责, 再在执行时确定真实状态承载模块落点。
- Modify: `src/assistant/motion_runtime.py`
  把跨周期状态 owner 与控制计算边界拆清。
- Modify: `src/assistant/app.py`
  切到新的状态入口并补清 owner 边界。
- Modify: `src/assistant/ctrl/chassis.py`
  移除对整周期运行时的别名暴露; `ctrl/` 只保留单周期控制计算, 不再作为跨周期状态或运行时 owner 的入口。
- Modify: `src/master/vision/state_machine.py`
  明确真实状态机职责, 防止继续外溢。
- Move/Modify: `src/master/stability/*.py`
  把仍有价值的能力并回控制相关目录, 并按职责命名。
- Move/Modify: `src/assistant/stability/*.py`
  把仍有价值的能力并回控制相关目录, 并按职责命名。
- Modify: `src/master/app.py`
  补清主车运行时 owner 的职责边界和导入边界。
- Modify: `src/master/motion_runtime.py`
  补清主车运行时 owner 的职责边界和导入边界。
- Modify: `tests/unit/master/test_runtime_params.py`
  保护主车常量边界。
- Modify: `tests/unit/assistant/test_runtime_params.py`
  保护辅车常量边界。
- Modify: `tests/unit/master/test_decision.py`
  切到真实 `master.vision.decision` 入口。
- Modify: `tests/unit/master/test_vision_ingress.py`
  切到真实 `master.vision.ingress` 入口。
- Modify: `tests/unit/master/test_vision_state_machine.py`
  切到真实 `master.vision.state_machine` 入口并保护状态机边界。
- Modify: `tests/unit/master/test_app.py`
  删除壳文件假设, 改成保护真实入口行为。
- Modify: `tests/unit/assistant/test_app.py`
  删除伪边界依赖, 改成保护真实入口和状态 owner 语义。
- Modify: `tests/unit/master/test_structure_runtime.py`
  删除低价值结构存在性测试, 只保留关键结构约束。
- Modify: `tests/unit/assistant/test_structure_runtime.py`
  删除低价值结构存在性测试, 只保留关键结构约束。
- Modify: `tests/unit/master/test_stability_baseline.py`
  跟随目录职责调整测试入口。
- Modify: `tests/unit/assistant/test_stability_baseline.py`
  跟随目录职责调整测试入口。
- Modify: `tests/unit/assistant/test_status.py`
  切到状态真实承载入口。
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
  切到状态真实承载入口。

### Task 1: 写出会失败的结构边界测试

**Files:**
- Modify: `tests/unit/master/test_runtime_params.py`
- Modify: `tests/unit/assistant/test_runtime_params.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **步骤 1：为参数边界写失败测试**

```python
def test_master_config_only_exposes_board_facts() -> None:
    import master.config as config

    assert hasattr(config, "UART_IDS")
    assert not hasattr(config, "CONTROL_TICK_MS")
```

- [ ] **步骤 2：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py -q`
Expected: FAIL, 失败点指向常量边界还不清楚。

- [ ] **步骤 3：为重复壳文件清理写失败测试**

```python
def test_master_tests_only_reference_real_vision_entrypoints() -> None:
    """这里应通过真实行为入口补测试

    目标是移除对旧壳入口的依赖, 证明真实入口已经成为唯一受支持入口,
    而不是继续保护壳文件是否存在。
    """
```

- [ ] **步骤 4：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_structure_runtime.py -q`
Expected: FAIL, 失败点指向真实入口尚未成为唯一受支持入口。

- [ ] **步骤 5：为入口收薄和状态收口写失败测试**

```python
def test_assistant_control_layer_does_not_own_cross_cycle_state() -> None:
    """这里应直接验证状态 owner 和控制层边界

    目标是证明单周期控制不再持有长期状态, 而不是验证某个新路径存在。
    """
```

- [ ] **步骤 6：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/assistant/test_structure_runtime.py tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: FAIL, 失败点指向状态入口缺失或入口仍然过厚。

### Task 2: 收口 `config.py` 和 `runtime_params.py` 边界

**Files:**
- Modify: `src/master/config.py`
- Modify: `src/assistant/config.py`
- Modify: `src/master/runtime_params.py`
- Modify: `src/assistant/runtime_params.py`
- Modify: `tests/unit/master/test_runtime_params.py`
- Modify: `tests/unit/assistant/test_runtime_params.py`

- [ ] **步骤 1：先盘点现有常量, 按“硬件事实 / 部署固定值 / 运行策略参数”分类**

- [ ] **步骤 2：逐项盘点 `config.py` 与 `runtime_params.py` 中全部常量, 标注为“硬件事实 / 部署固定值 / 运行策略参数”**

- [ ] **步骤 3：把不属于当前文件职责的常量迁移到正确入口, 并同步更新调用点**

- [ ] **步骤 4：只整理职责边界, 不引入新的参数层或兼容层**

- [ ] **步骤 5：运行参数边界测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py -q`
Expected: PASS。

### Task 3: 删除主车重复入口壳并切到真实目录入口

**Files:**
- Delete: `src/master/decision.py`
- Delete: `src/master/vision_ingress.py`
- Delete: `src/master/vision_state_machine.py`
- Modify: `src/master/status.py`
- Modify: `tests/unit/master/test_decision.py`
- Modify: `tests/unit/master/test_vision_ingress.py`
- Modify: `tests/unit/master/test_vision_state_machine.py`

- [ ] **步骤 1：删除主车重复概念壳文件**

- [ ] **步骤 2：先确认 `master/status.py` 是否仅为转手导出; 只有在确认无真实职责后才删除**

判定标准: 若主链、协议输出或日志仍直接依赖 `master.status` 中的非转手实现, 则保留并补职责注释; 若这里只剩转手导出, 则删除并把调用点统一切到真实入口。

- [ ] **步骤 3：把测试和调用切到真实 `vision/` 目录入口**

```python
from master.vision.decision import decide_from_observation
```

- [ ] **步骤 4：运行相关测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_decision.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py tests/unit/master/test_structure_runtime.py -q`
Expected: PASS。

### Task 4: 收薄主辅入口装配

**Files:**
- Modify: `src/master/main.py`
- Modify: `src/assistant/main.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`

- [ ] **步骤 1：让入口测试先暴露多余装配层级**

```python
def test_master_main_only_handles_boot_dispatch() -> None:
    """这里应验证入口只承担最小启动职责

    例如按键分支、运行时启动分发和主循环进入仍成立,
    同时不再暴露额外装配中转语义。
    """
```

- [ ] **步骤 2：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: FAIL, 失败点指向入口仍暴露额外装配中转或懒加载入口。

- [ ] **步骤 3：只保留板端根目录直烧所需的最小入口逻辑**

- [ ] **步骤 4：运行入口相关测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

### Task 5: 收口辅车跨周期状态与状态序列化

**Files:**
- Create if needed: `src/assistant/state/*`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/ctrl/chassis.py`
- Modify: `tests/unit/assistant/test_status.py`
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

边界说明:
- 对外状态回传只负责最小状态文本和序列化
- 运行时长期状态仍由唯一 owner 持有
- 控制层只保留单周期计算, 不接管长期状态, 不暴露运行时 owner
- 若确有独立、跨周期、非控制计算、非硬件句柄的状态需要收口, 再建立 `state/`; 否则只明确 owner 和调用边界
- 本任务只调整状态 owner 和序列化归属, 不修改现有最小状态回传契约的字段名、必带字段、状态集合和关联规则

- [ ] **步骤 1：把“谁持有长期状态、谁负责序列化、控制层不持有长期状态”的失败测试补齐**

- [ ] **步骤 2：先冻结辅车当前最小状态回传基线样例和断言, 再开始重构**

```python
def test_assistant_state_owner_and_serializer_boundary() -> None:
    """这里应验证长期状态 owner 和对外序列化边界

    目标是证明控制层不再持有长期状态, 且对外状态文本由明确入口负责。
    """
```

- [ ] **步骤 3：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/assistant/test_status.py tests/unit/assistant/test_structure_runtime.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: FAIL, 失败点指向长期状态 owner、序列化入口或控制层边界仍然混杂。

- [ ] **步骤 4：若确有独立状态职责, 则在执行时确定真实状态承载模块并迁移状态与序列化; 否则仅调整 owner 和调用边界**

- [ ] **步骤 5：保持主链行为不变, 只调整 owner 和导入边界**

- [ ] **步骤 6：所有对 `ChassisRuntime` / `MotionRuntime` 的对外入口, 统一切到运行时 owner 所在模块; `ctrl/` 不再暴露整周期运行时**

- [ ] **步骤 7：合同测试继续校验重构前的最小状态回传契约, 不允许通过同步修改预期来放宽契约**

- [ ] **步骤 8：运行状态与协议测试确认通过**

Run: `python3 -m pytest tests/unit/assistant/test_status.py tests/unit/assistant/test_structure_runtime.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS。

### Task 6: 梳理真实状态机边界

**Files:**
- Modify: `src/master/vision/state_machine.py`
- Modify: `tests/unit/master/test_vision_state_machine.py`

- [ ] **步骤 1：为状态机边界写失败测试**

```python
def test_state_machine_only_carries_phase_transition_semantics() -> None:
    """这里应验证状态机只负责阶段切换

    测试要沿用当前真实对外语义, 只证明它没有承担控制、协议或硬件职责,
    不预设新的返回字段集合。
    """
```

- [ ] **步骤 2：运行测试确认按预期失败或暴露职责漂移**

Run: `python3 -m pytest tests/unit/master/test_vision_state_machine.py -q`
Expected: FAIL 或出现状态机继续承担控制、协议或硬件职责的迹象。

- [ ] **步骤 3：整理状态机职责, 保证只保留阶段切换语义, 并沿用当前真实入口对外语义, 不额外改写返回格式**

- [ ] **步骤 4：运行状态机测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_vision_state_machine.py -q`
Expected: PASS。

### Task 7: 合并 `stability/` 到更准确职责目录并清理低价值测试

**Files:**
- Move/Modify: `src/master/stability/*.py`
- Move/Modify: `src/assistant/stability/*.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`
- Modify: `tests/unit/master/test_structure_runtime.py`
- Modify: `tests/unit/assistant/test_structure_runtime.py`

- [ ] **步骤 1：先把目录迁移影响写成失败测试**

```python
def test_stability_math_returns_to_real_control_owner() -> None:
    """这里的断言应基于当前仍被使用的稳定性计算真实入口补写

    目标是证明这部分能力已经回到真实控制责任方, 且旧壳假设已移除,
    不允许用新目录名、新模块名或新文件名作为断言目标。
    """
```

- [ ] **步骤 2：运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py -q`
Expected: FAIL, 失败点指向这部分能力的真实责任方仍不清楚, 或旧壳假设仍未清理。

- [ ] **步骤 3：迁移仍有价值的计算能力到更准确职责目录**

仅迁移仍被真实入口引用的能力; 未被主链使用的内容不在本轮处理。

- [ ] **步骤 4：删除只验证目录存在和壳导出的低价值结构测试**

- [ ] **步骤 5：运行相关测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/assistant/test_stability_baseline.py tests/unit/master/test_structure_runtime.py tests/unit/assistant/test_structure_runtime.py -q`
Expected: PASS。

### Task 8: 按规则补注释并做总回归

**Files:**
- Modify: `src/master/app.py`
- Modify: `src/assistant/app.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify if needed: `Task 5` 最终确定的状态承载模块
- Modify: `src/master/vision/state_machine.py`

- [ ] **步骤 1：补职责、边界和保留原因注释**

- [ ] **步骤 2：删除复述式空注释**

- [ ] **步骤 3：跑本轮针对性测试**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/master/test_decision.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py tests/unit/assistant/test_status.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS。

- [ ] **步骤 4：跑主机侧联合回归**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **步骤 5：记录最小内存留证**

留证至少包含:
- 导入后最小可用内存
- 核心初始化后最小可用内存
- 功能初始化后最小可用内存
- 空闲运行时最小可用内存
- 低内存下最小诊断面是否仍可用
- 本轮新增或保留的常驻项是什么
- 每个常驻项的唯一归属是谁
- 它在哪个阶段出现
- 为什么必须保留
- 是否影响最小诊断面

### Task 9: 做板端最小验证与留证

**Files:**
- Create: `tests/hil/2026-04-01-master-minimal-runtime.md`
- Create: `tests/hil/2026-04-01-assistant-minimal-runtime.md`

- [ ] **步骤 1：按最小板端流程验证主车入口仍可启动**

固定顺序:
- `mpy-cli list`
- `mpy-cli plan`
- 上传并运行
- 最小 smoke
- 最小查询
- 留证

Run: `mpy-cli list`
Expected: 能看到目标设备。

- [ ] **步骤 2：执行主车固定动作链并记录结果**

Run: `mpy-cli plan`
Expected: 设备路径与上传计划可用。

Run: `mpy-cli deploy --port <master-port>`
Expected: 主车目录上传并进入启动流程。

Run: `python3 tools/run_stage2_smoke.py --port <master-port> --source-dir src/master`
Expected: 主车最小 smoke 可复核。

固定动作链:
- 设备发现
- `mpy-cli plan`
- 上传/运行
- 最小 smoke 或最小查询
- 记录观测结果
- 形成主车结论

主车留证至少包含:
- 设备端口或设备标识
- 上传/运行命令
- 最小 smoke 或最小查询结果
- 启动是否进入主循环, 禁止只凭“有串口输出”判通过
- 主车最小诊断面是否仍可用
- 失败时的现象、时间点和归因线索

- [ ] **步骤 3：上传并运行主车根目录入口, 观测最小启动输出**

- [ ] **步骤 4：执行辅车固定动作链并记录结果**

Run: `mpy-cli list`
Expected: 能看到目标设备。

Run: `mpy-cli plan`
Expected: 设备路径与上传计划可用。

Run: `mpy-cli deploy --port <assistant-port>`
Expected: 辅车目录上传并进入启动流程。

Run: `python3 tools/run_stage2_smoke.py --port <assistant-port> --source-dir src/assistant`
Expected: 辅车最小 smoke 可复核。

固定动作链:
- 设备发现
- `mpy-cli plan`
- 上传/运行
- 最小 smoke 或最小查询
- 记录观测结果
- 形成辅车结论

辅车留证至少包含:
- 设备端口或设备标识
- 上传/运行命令
- 最小 smoke 或最小查询结果
- 启动是否进入主循环, 禁止只凭“有串口输出”判通过
- 辅车最小状态回传是否仍符合现有契约
- 失败时的现象、时间点和归因线索

- [ ] **步骤 5：上传并运行辅车根目录入口, 观测最小启动输出和最小状态回传**

通过条件:
- 主车: 能证明已进入主循环且最小诊断面仍可用
- 辅车: 能证明已进入主循环且最小状态回传仍符合重构前契约
- 两侧都禁止只凭“有串口输出”判通过

- [ ] **步骤 6：把主车和辅车的板端最小验证步骤、观测结果和结论分别留到 `tests/hil/`**

- [ ] **步骤 7：确认主机侧通过不替代板端最小验证**

## 完成标准

- 主线代码中不再保留重复概念壳文件。
- 主辅入口装配明显收薄, 但板端根目录语义仍成立。
- `config.py` 与 `runtime_params.py` 的职责边界有测试保护。
- 辅车跨周期状态与控制边界清楚可读。
- 状态机边界有测试保护, 不再继续外溢。
- `stability/` 不再作为独立弱语义目录存在。
- 低价值结构测试被删除, 行为测试保持完整。
- 注释能清楚说明职责、边界和保留原因。
- 最小内存留证可供复核, 最小诊断面仍可用。
- 主机侧通过不等于完成, 板端最小链路验证与留证完成后才允许收口。
