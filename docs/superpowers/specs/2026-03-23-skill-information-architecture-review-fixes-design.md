---
title: Skill 信息架构评审修正设计
date: 2026-03-23
status: draft
scope: .agents/skills, docs/developer, skill-owned references and assets
supersedes:
  - docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md
---

# 背景

`docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md` 已经推动仓库完成了一轮 Skill 外壳重组，包括新入口命名、本地扩展 Skill 落地、`mpy-cli-tool` 路由化以及旧知识型 Skill 删除。

但本轮 review 明确指出，当前结果仍存在 3 类核心问题：

1. **规则丢失风险真实存在**：重构优先处理了外壳和入口，但旧 `code-standards`、`embedded-development`、`control-system` 中的大量规则并没有逐条归位，导致仓库约束被削弱。
2. **人工 review 面仍然过大**：`memory-review`、`transportcar-memory-assets`、`tdd-workflow`、`harness-design-pattern` 这类内容更适合由 Agent 使用和执行，不应继续作为需要用户人工 review 的主正文。
3. **路由与引用页仍偏碎**：当前 references 数量偏多，部分入口只是换名字指向相近内容，容易让 Agent 在路由时产生歧义。

因此，本设计不是重写整套方案，而是对现有方案做**评审修正**：

- 保留已经成立且不冲突的结构结论
- 把本轮 review 的意见提升为最高优先级
- 逐条追回旧规则
- 重新划定“哪些内容给用户 review，哪些内容交给 Agent 自己负责”

这里的“追回旧规则”有一个明确前提：

- 旧规则的事实依据不仅来自当前工作区，也来自仓库 Git 历史
- 若旧 Skill 文件已在当前工作区删除，不得因此视为对应规则已经失效
- 后续实施必须先从 Git 历史中恢复旧 Skill 内容，再做逐条归位

# 本次修正的最高优先级

本轮 review 的新增要求具有最高优先级。凡与这些要求冲突的旧结论，一律以本节为准。

最高优先级要求如下：

1. 旧 Skill 中原有规则不得因重构而丢失，必须逐条补回。
2. `docs/developer/` 最终只保留用户需要人工 review 的正文：`strategy.md` 与 `tasks.md`。
3. `memory-review`、`transportcar-memory-assets`、`tdd-workflow`、`harness-design-pattern` 不再作为用户人工 review 的正文，应转为 Agent 私有知识或 Skill 内部依据。
4. memory 相关评估默认由 AI 执行，不再要求用户承担机械、量化的 memory review 工作。
5. 能合并的 references 与入口必须合并，禁止为了目录完整性保留高重复率、低区分度的路由页。
6. 旧 Skill 规则的追回不得只依赖当前工作区；若当前文件已删除，必须把 Git 历史记录作为正式规则来源之一。

# 继承清单

以下结论继续从 `docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md` 继承，并在本次修正后仍然有效：

1. 仓库知识主入口继续使用 `using-rules`。
2. 仓库参考维护入口继续使用 `reference-sync`。
3. 扩展 superpowers 的本地 Skill 继续使用 `project-extension-*` 前缀，不采用同名覆盖方案。
4. `project-extension-writing-skills` 与 `project-extension-requesting-code-review` 继续保留为本地扩展 Skill。
5. `mpy-cli-tool` 继续保留为独立工具型 Skill，而不是并回知识总入口。
6. `code-standards`、`control-system`、`embedded-development`、`remote-spec-to-markdown` 继续作为已废弃旧 Skill，不恢复为顶层主入口。
7. “主 Skill 短入口 + 详细知识下沉”的总方向继续保留。

# 覆盖清单

以下旧结论虽在上一版设计中出现，但现被本轮 review 明确覆盖：

1. **覆盖旧结论：** 只要完成入口重组和旧 Skill 删除，就可以视为重构完成。
   - **新结论：** 没有完成旧规则逐条迁回前，重构不得视为完成。

2. **覆盖旧结论：** `docs/developer/` 可继续承载 memory、TDD 等 Agent 执行型知识。
   - **新结论：** `docs/developer/` 只保留 `strategy.md` 与 `tasks.md`，其余执行型知识迁出。

3. **覆盖旧结论：** references 可以按主题充分拆分，只要形式上是“单一正文 + 引用页”。
   - **新结论：** 引用页必须以降低歧义为目标，能合并就合并，不得保留高重复率入口。

4. **覆盖旧结论：** memory 相关内容主要作为用户可见正文存在。
   - **新结论：** memory 相关内容转为 Agent 私有依据，默认由 AI 负责检查与评估。

5. **覆盖旧结论：** `harness-design-pattern` 可继续作为用户 review 主正文。
   - **新结论：** `harness-design-pattern` 迁入 `project-extension-writing-skills` 的 Skill 私有体系，不再作为用户主 review 正文。

# 目标

本轮修正的目标只有 4 个：

1. 保证旧 Skill 规则一条不少地重新归位。
2. 把用户需要 review 的正文面收缩到最小，只保留战略与任务两类内容。
3. 把适合 Agent 自行执行的规则迁入 Skill 私有体系。
4. 压缩重复入口，让 Skill 路由更直接、更稳定。

# 文档归属修正

## 用户人工 review 的正文

`docs/developer/` 最终只保留：

- `docs/developer/strategy.md`
- `docs/developer/tasks.md`

用户后续主要 review：

- 当前仓库的目标、边界与优先级
- 当前任务拆解与阶段目标

## Agent 私有正文 / Skill 私有依据

以下内容不再作为用户人工 review 的主正文，后续迁入 Skill 内部维护：

- `docs/developer/memory-review.md`
- `docs/developer/transportcar-memory-assets.md`
- `docs/developer/tdd-workflow.md`
- `docs/harness-design-pattern.md`

迁移后的原则：

- 用户不再被要求人工执行 memory 量化检查
- 用户不再被要求 review TDD 流程细节
- 用户不再被要求 review Skill 编写方法论
- 这些内容改由 Agent 在实现、review、写 Skill 时主动查阅和执行

## memory 相关内容的职责修正

memory 相关内容不再作为用户要 review 的正文，而是作为 Agent 的私有评估依据：

- AI 在实现前应主动做 memory 约束自查
- AI 在收口时应主动做 memory 影响评估
- 用户只需 review 结果是否值得保留、是否符合任务目标，不承担具体 memory 量化工作

# 新的 Skill 职责边界

## `using-rules`

只承接**实现阶段**需要查询的规则，包括：

- 通用实现规则
- 架构边界
- 硬件与协议事实
- 控制与比赛策略
- 实现阶段需要的 memory 护栏
- 实现阶段需要的 TDD / 嵌入式流程护栏

不再承接：

- 用户人工 review 正文
- Skill 编写方法论

## `project-extension-requesting-code-review`

只承接**AI 收口阶段**的自检与评审规则，包括：

- 满足要求
- 最小改动
- 正贡献
- 风格一致性
- memory 影响评估

其中 memory 检查默认由 AI 执行，不再作为用户的人工 review 负担。

## `project-extension-writing-skills`

承接 Skill 写作与改造规范，包括：

- Harness 设计模式
- Skill 命名与目录规范
- references / assets 的使用约束
- 旧 Skill 向新结构迁移的检查清单

## `reference-sync`

继续负责：

- 外部资料同步
- Markdown 清洗
- 来源追溯
- Skill 私有知识与 `docs/` 正文之间的更新流程

## `mpy-cli-tool`

继续保留独立，但路由进一步收缩：

- 命令与路径边界
- 排障入口

不再保留过多细碎二级入口。

# 路由收缩原则

后续所有 references 重构必须遵守以下原则：

1. 同一份正文若多个入口没有明确时机场景差异，则必须合并。
2. 一个 Skill 的引用入口数量应尽量少，以“最短决策路径”为目标。
3. 禁止保留仅仅改了文件名、但实际阅读建议几乎一样的入口页。
4. 若一个领域本质上只需要“总入口 + 1 个补充入口”，不得为了形式拆成 4 到 5 个入口。
5. references 的目的应是**降低选择成本**，而不是展示分类完整性。

# 旧 Skill 规则逐条迁移表

本节是本设计的主体。后续实现必须逐条迁移，不得概括带过。

这些规则的来源分为两类：

1. 当前工作区仍可读取的现有正文
2. 已在当前工作区删除、但必须从 Git 历史中追回的旧 Skill 内容

后续实施时，若某条规则当前只存在于 Git 历史中，也必须先恢复并纳入迁移表，再决定归属，不得因为文件已删而跳过。

## 一、旧 `code-standards` 规则迁移

### A. 迁入 `using-rules` 的实现阶段规则

- 目标平台是 RT1021 + MicroPython，本地开发兼容 Python 3.8+
- 运行时代码默认不要依赖 `typing`，若必须使用类型辅助，要采用不影响板端导入的写法
- 注释和文档字符串统一使用中文
- 文档注释统一采用 Doxygen 风格，默认使用 `@brief`，按需补充 `@param`、`@return`、`@note`、`@warning`
- 注释中的标点统一使用半角符号，且标点后加空格
- 单行注释行尾不加句号、逗号、分号、冒号等收尾标点
- 对复杂流程、状态机分支、lazy 装配、兼容桥接和非显然控制逻辑，必须补中文块注释
- 函数、类和模块必须有中文 Doxygen 文档注释，说明输入、输出、副作用和关键约束
- 行数门禁按非注释代码行计算，注释和空行不计入
- 一个领域拆成 2 个以上实现文件时，必须优先改为包目录加 `__init__.py`
- 禁止使用共同前缀平铺文件模拟命名空间
- 魔法数字集中到 `config/params.py`
- 禁止静默失败，只捕获预期异常并保留上下文
- `hardware` 只放硬件驱动与总线访问，不放业务逻辑
- `control` 只放 PID、运动学、轨迹、姿态估计等控制算法
- `filters` 只放独立可复用滤波算法
- `services` 只做编排，不承载底层算法、设备访问细节或隐藏状态机
- `vision` 或独立领域包只放视觉协议、状态机和领域转换逻辑，不混入服务编排
- `storage` 只负责持久化
- `config` 只负责配置与常量
- `utils` 只放通用纯函数工具
- 依赖方向必须保持单向，禁止下层反向依赖上层，禁止循环依赖与跨层跳跃调用
- 一个运行时状态只能有一个主拥有者
- 模块协作必须通过显式接口、受控数据结构或明确协议完成
- command handler、query handler、facade、adapter 不得直接读写宿主内部字段或临时属性
- import-time 自动注册必须 fail-fast、可观测、可验证
- diagnostics 只能只读聚合 owner 状态，不得缓存第二份运行时状态
- command / query 装配默认应显式延迟加载，不得回退到 import-time 全量注册
- 对 `TransportCar`、运行时 owner、诊断 facade、命令装配和板端 probe 的改动，首要目标是最小内存占用指标
- 新增常驻对象必须说明 owner、阶段、A / B / C / D / E 分类、触发条件和必要性
- import-time 禁止目录扫描、自动发现、自动注册和重型单例初始化
- 模块级可变运行时全局状态属于阻断项
- 可延迟功能若被重新放回构造期无条件初始化，直接不通过
- 热路径新增大字符串拼接、大临时容器或无解释动态分配时，必须给出必要性证明
- 结构更清晰但内存指标未改善，不算有效重构
- 没有 2 个以上真实消费者时，不要引入通用框架式抽象
- 不要为未来假设需求提前引入事件总线、插件系统或多层适配器链
- 若新增抽象只是搬运复杂度，但没有降低理解成本或测试成本，视为过度设计

### B. 迁入 `project-extension-requesting-code-review` 的收口规则

- 代码是否位于正确分层目录
- 是否存在上层反向依赖或循环依赖
- 是否满足类型提示、中文文档和异常处理要求
- 是否将参数和阈值集中到 `config/params.py`
- 是否满足 5ms 控制周期下的性能约束
- 是否存在状态单一所有权不明、状态双写或状态泄漏
- 是否通过私有字段、临时属性或隐式上下文协议耦合多个模块
- 是否为了未来假设需求引入没有现实收益的抽象
- 是否把算法细节、设备细节或领域状态继续堆进编排层
- 是否把 import-time 副作用当作默认装配方式，且缺少失败可观测性
- 是否给出了 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle` 和 `diag_survival` 证据
- 是否说明了新增常驻对象为什么属于 A / B 类，而不是 C / D 类
- review 输出不能停留在表面结论，必须明确职责边界、状态归属、耦合方式和抽象成本是否健康

## 二、旧 `embedded-development` 规则迁移

### A. 迁入 `using-rules` 的实现阶段规则

- 行为改动必须先选测试层：`unit` / `contract` / `HIL`
- 行为改动必须先有失败测试，主机侧通过只是起点，不是终点
- `tests/unit` 用于纯逻辑、确定性算法、解析器、路由、存储、工具函数
- `tests/contract` 用于命令处理器、协议路由、副作用契约
- `tests/hil` 是真实设备、真实时序、真实外设、真实控制循环的最终留证层
- 进入设备路径的判据包括：修改 `src/hardware/`、修改 `src/services/transport_car.py`、依赖真实串口/编码器/IMU/电机/ticker、需要证明 5ms 预算或真实动作链路
- `stage2` 只做 MPY smoke，不验证真实硬件动作
- `stage3` 通过 `uart3` 做人工观测和故障归因，不是自动 PASS / FAIL
- `HIL` 必须留下步骤、预期、实际输出和 PASS / FAIL 结论
- 每个外设一个独立模块，接口最小化，业务编排放 `services`
- 驱动层不夹带业务逻辑
- 已知 `src/boot.py` 的 Button 1-4 引脚分别是 `C8`、`C9`、`C14`、`C15`
- 已知 `src/boot.py` 的 D8/D9 带上拉，`1` 表示开关关闭，`0` 表示开关闭合
- 任何仓库或用户未明确给出的硬件引脚、接线、板级资源映射都必须先问用户，禁止猜测
- 串口处理默认非阻塞
- PWM、方向切换与占空比限幅要原子化处理
- 中断回调只置标志，不执行重计算或阻塞 I/O
- 关键路径避免动态分配和大字符串操作
- 新增逻辑必须评估耗时，建议用 `ticks_us` 量测
- 控制周期超预算时，先降复杂度，再讨论新特性
- 电机方向、编码器方向与运动学坐标系必须一致
- IMU 设备 ID、零漂校准文件和读数稳定性必须可验证
- 视觉对正语义必须以 `references/openart-protocol.md`、`src/services/vision_protocol.py`、`src/services/vision_state_machine.py` 为准
- 若看到 `src/control/kinematics.py` 中旧注释，视为历史残留，不得拿来推断当前协议方向
- 车体系方向固定为 `y+` 前进、`x+` 右移、`omega+` / `d_angle+` 顺时针
- `dx/dy/d_angle` 是车体系相对增量，`x/y/angle` 是世界系绝对目标
- 视觉输入只认 `UART6` 上完整框 `left/top/right/bottom`
- OpenArt 传入的 `left/top/right/bottom` 已经是最终画面坐标，主控侧不得再次翻转
- `ALIGN_ANGLE`、`ALIGN_DIST`、`ALIGN_DX`、`ORBITING`、`PUSHING`、`RETURNING` 的符号关系和解释口径必须保持一致
- 没有 HIL 证据前，不得把 `push_angle_deg = -90` 口头改写为绝对物理方向
- 任何“左 / 右 / 前 / 后 / 顺时针 / 逆时针”描述都必须带参考系
- `uart3` 观测或 `tests/hil/` 留证前，必须先验证完整框、`obs_center_x`、`obs_bottom`、阶段顺序和 `UART6` 上旧 `x,y` 的吞掉行为

### B. 迁入 `project-extension-requesting-code-review` 的收口规则

- 不允许“先把代码写完再补测试”
- 不允许“主机测试过了，就不用上板了”
- 不允许“直接让车动一下看看”替代设备门禁流程
- 不允许跳过 `stage2` 直接看 `stage3`
- 不允许“看到串口有输出就算完成”
- 不允许“HIL 以后再补”
- 进入设备路径后，交付物必须包含主机测试、设备命令、smoke 输出、观测输出、失败归因和 HIL 证据

## 三、旧 `control-system` 规则迁移

### A. 迁入 `using-rules` 的实现阶段规则

- 控制层级固定为位置环 -> 速度环 -> PWM 输出
- 反馈来源固定为编码器 + IMU
- 控制模式包括速度模式、位置模式、角度保持模式
- 改算法前必须先确认编码器方向、电机方向和 IMU 校准等硬件基线
- 参数辨识先行，使用 `pid_identify.py` 生成最新电机参数
- 关键参数统一在 `config/params.py`，禁止散落阈值
- 控制相关跨模块改动必须保持 `services` 只做编排，算法实现留在 `control` 和 `filters`
- 控制周期预算默认 5ms，新增计算必须评估耗时
- 调参顺序固定为：校准陀螺仪 -> 重新辨识电机 -> 只开速度环调内环 -> 打开位置环调外环 -> 调航向保持 -> 做组合轨迹联调
- 振荡时先降 P，再增 D，检查滤波与周期抖动
- 响应慢时增 P、减滤波延迟、核对前馈
- 稳态误差时补 I 或校正前馈，并复核辨识参数
- 航向漂移时重做 IMU 零漂，检查积分与 `dt`
- 轨迹偏差时检查打滑、最大速度、加速度限制

### B. 迁入 `project-extension-requesting-code-review` 的收口规则

- 单轮和三轮协同控制都必须通过
- 速度模式、位置模式、模式切换都必须通过
- `?lock` 相关行为必须与相对位移命令一致
- 长时间运行不得出现明显航向漂移失控
- 交付物必须包含控制算法或参数变更说明、调参与验证记录，必要时补充回归测试脚本或验证命令

## 四、迁入 `project-extension-writing-skills` 的规范

本次 review 没有要求恢复一个独立旧 Skill 写作入口，但已经明确要求：Skill 编写方法论不应继续让用户在主正文里 review。

因此以下内容应收进 `project-extension-writing-skills`：

- `harness-design-pattern` 的正文与方法论
- 本仓库 Skill 命名、目录和 references / assets 约束
- 旧 Skill 向新结构迁移时的检查清单
- 如何避免在 Skill 重构中丢规则的操作规范

# 验收标准

只有同时满足以下条件，本轮修正才算完成：

1. 旧 `code-standards`、`embedded-development`、`control-system` 中的规则已逐条完成归位，没有遗漏项。
2. `docs/developer/` 只剩 `strategy.md` 与 `tasks.md`。
3. `memory-review`、`transportcar-memory-assets`、`tdd-workflow`、`harness-design-pattern` 已迁出用户主 review 正文范围。
4. memory 相关规则已明确变成 AI 自行检查项，而不是用户人工评估项。
5. `using-rules`、`project-extension-requesting-code-review`、`project-extension-writing-skills` 的职责边界清晰，没有重复承载同类规则。
6. references 数量已按“能合并就合并”的原则收缩，不再保留明显重复入口。
7. 历史已废弃 Skill 不重新恢复为主入口，但其规则内容完整保留在新结构中。

# 当前建议的后续实施顺序

1. 先按本 spec 生成新的实施计划
2. 先从 Git 历史恢复旧 Skill 内容，形成完整规则盘点清单
3. 再做“旧规则逐条迁回”与“正文迁移边界修正”
4. 再做 references 合并与路由收缩
5. 最后统一验证哪些内容还需要用户 review，哪些内容完全转为 Agent 私有知识
