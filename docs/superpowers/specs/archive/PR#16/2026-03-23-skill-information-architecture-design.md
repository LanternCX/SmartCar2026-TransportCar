---
title: Skill 信息架构重组设计
date: 2026-03-23
status: approved
scope: .agents/skills and skill-owned references
---

# 背景

当前仓库里的 Skill 已经出现两类结构问题：

1. 知识型 Skill 承载了过多仓库知识, Agent 一旦触发 Skill 就会整份读取, 上下文效率偏低。
2. 一些工具型 Skill 同时承担“使用入口”和“参考手册”两种职责, 高频调用时会造成不必要的上下文膨胀。

用户明确提出本次重构的核心目标不是单纯拆小文档, 而是建立“路由 + 渐进式披露”的结构：

- 常驻上下文里真正长期存在的是 Skill `description`
- Agent 触发 Skill 后会读取 `SKILL.md` 全文
- 因此主 `SKILL.md` 应尽量短, 只承担路由和门禁职责
- 具体知识、规则、协议和长参考应下沉到 Skill 自己的 `references/` 文档里
- Agent 应被引导到特定领域主动查询, 而不是一次吞下全部仓库知识

另外, `docs/harness-design-pattern.md` 给出了更适合当前目标的 Harness 结构：

- 知识入口优先采用 `Tool Wrapper`
- 审查标准可借用 `Reviewer`
- 高频工具 Skill 也可改造成“短入口 + references”模式

# 用户确认的设计约束

## Skill 分类判断

- `code-standards`、`control-system`、`embedded-development` 属于知识型 Skill, 需要整合
- `mpy-cli-tool`、`remote-spec-to-markdown` 属于工具/能力型 Skill, 不应与知识型 Skill 合并
- `using-git-worktrees`、`git-workflow` 属于流程型 Skill, 保持独立

## 工具型 Skill 的处理原则

- 低频工具型 Skill 不必为了形式统一而强行瘦身
- 高频工具型 Skill 需要适度精简, `mpy-cli-tool` 是当前最明确的对象
- 对于高频工具型 Skill, 主 `SKILL.md` 只保留入口索引和路由, 详细说明放到大文档中

## 文档归属原则

- 面向 Agent 按需读取的参考文档, 应优先放在对应 Skill 目录内部
- 不应把本质上属于 Skill 私有知识源的文档长期放在仓库根 `docs/` 下
- 用户当前特别指出: `mpy-cli-tool` 与 `Protocol` 相关 Markdown 需要重新审视归属, 倾向迁入 Skill 体系内

以上判断在后续迁移中已进一步收敛为“单一正文事实源”原则：

- 正文只维护一份, 避免双份知识长期漂移
- `mpy-cli` 正式正文已迁入 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- OpenArt 协议正式正文已迁入 `.agents/skills/using-rules/references/openart-protocol.md`
- 有些正式正文仍保留在 `docs/`, 但 `mpy-cli` 与 OpenArt 协议这类已迁入对应 Skill 的内容, 唯一事实源已经不在根 `docs/`
- Skill 的 `references/` 不复制正文, 而是通过引用页路由到当前正式落点
- 根 `docs/` 下对应旧路径已删除; 本文若提到旧方案, 只用于保留迁移语境, 不再作为活动事实源

## 新的能力拆分方向

- 规则与仓库知识的“使用”应与“更新维护”拆开
- 新增一个规则使用入口 Skill, 名称倾向通用化, 如 `using-rules`
- 新增一个文档维护入口 Skill, 暂定为 `reference-sync`
- `remote-spec-to-markdown` 的能力应考虑并入 `reference-sync`, 作为文档同步/清洗流程的一部分
- 需要在仓库内新增一个本地 Skill 编写/改造入口, 用于在 superpowers `writing-skills` 基础上叠加本仓库自己的 Harness 设计模式
- 需要在仓库内新增一个本地代码评审 Skill, 用于补充 superpowers `requesting-code-review` 未覆盖的仓库本地审查标准

# 设计目标

1. 让 Agent 在命中仓库知识类 Skill 时, 优先读取最短的路由说明, 再按主题读取具体参考文档。
2. 消除 `code-standards`、`control-system`、`embedded-development` 之间的知识重叠与重复入口。
3. 保留工具型 Skill 与流程型 Skill 的独立性, 仅对高频 Skill 做结构化瘦身。
4. 把 Skill 私有参考文档迁回 Skill 目录内部, 让文档归属与实际使用方式一致。
5. 为后续“从 GitHub 或远端资料更新参考文档”预留统一维护入口。
6. 为后续所有 Skill 的新建、改造和审查提供仓库本地的写作/结构规范入口。
7. 为功能完成后的最终收口提供仓库本地的代码评审入口, 覆盖最小改动、风格一致性和内存占用风险。

# 设计原则

## 总原则: 竞赛结果导向优先于通用工程审美

当前仓库首先是竞赛项目, 不是通用产品工程。所有本地 Skill, 尤其是规则使用与代码评审相关 Skill, 都必须先服从以下总原则：

- 能不加功能就不加功能, 避免为了“更完整”继续扩展改动面
- 能少占内存就少占内存, MicroPython 运行时内存是核心约束, 不是次要指标
- 能更精简就不引入额外层次, 不为了结构好看增加抽象、包装和常驻对象
- 若“结构更优雅”和“更容易稳定完赛”冲突, 优先选择后者
- 若“更通用”与“更省内存、更可控、更易验证”冲突, 优先选择后者

## 原则 1: 主 Skill 只做路由, 不做百科

主 `SKILL.md` 的内容应限制在以下职责内：

- 什么时候必须触发这个 Skill
- 当前任务属于哪个知识领域
- 命中某领域后必须读取哪份参考文档
- 哪些高风险场景不查参考就不能继续

不应把完整定义、长篇规则、详细协议、命令参数手册继续堆在主 `SKILL.md` 中。

## 原则 2: references 才是知识承载层

知识型 Skill 下的 `references/` 应成为仓库规则与背景知识的主要承载位置。

这些参考文档可以按主题拆分, 例如：

- 代码风格
- 架构边界
- 内存门禁
- 嵌入式验证流程
- 硬件事实
- 视觉语义
- 控制系统知识
- 协议参考

在当前仓库里, `references/` 更准确的职责不是“复制存放一份新的正文”, 而是“为 Skill 提供稳定的引用入口”。

默认做法应为：

- 正式正文只保留一份, 具体落点按文档归属决定
- 仍面向全仓库共用的人类正文可以保留在 `docs/`
- 已明显归属某个 Skill 的正式正文可直接放在该 Skill 的 `references/` 中维护, 如 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` 与 `.agents/skills/using-rules/references/openart-protocol.md`
- `references/` 负责提供稳定入口并路由到当前唯一事实源, 不再默认假定底层正文一定在根 `docs/`

## 原则 3: 使用与维护分离

- `using-rules` 负责“怎么查规则, 什么时候查规则”
- `reference-sync` 负责“怎么更新规则文档, 如何从外部来源同步进仓库”

日常开发场景默认只触发 `using-rules`, 不应把文档维护流程混入日常使用入口。

## 原则 4: 高频工具 Skill 采用轻量路由模式

像 `mpy-cli-tool` 这样高频且内容容易膨胀的工具型 Skill, 应采用：

- 主 `SKILL.md` 提供命令索引和场景路由
- 长参考文档下沉到 Skill 内部文档
- Agent 根据命令或问题类型再跳到对应大文档

## 原则 5: Skill 编写规范采用“上游通用方法 + 仓库本地扩展”

- 不直接改写 superpowers 自带的 `writing-skills`
- 在仓库内新增一个本地 Skill, 作为 Skill 编写与改造的补充规范入口
- 该本地 Skill 应继承 `writing-skills` 的通用方法, 再叠加本仓库的 Harness 设计模式、目录约定和命名约束
- `docs/harness-design-pattern.md` 的知识应迁入该本地 Skill 自己的 `references/` 中维护

## 原则 6: 扩展 superpowers 的本地 Skill 使用统一前缀命名

- 不使用与 superpowers 完全同名的 Skill, 避免本地覆盖上游 Skill 并造成双份维护负担
- 只有明确用于扩展 superpowers 的本地 Skill 才使用 `project-extension-` 前缀
- 命名统一采用“主语 + 谓语”结构, 其中主语是 Skill 类别, 谓语是目标动作或对象
- 例如: `using-rules`, `reference-sync`, `project-extension-writing-skills`, `project-extension-requesting-code-review`
- 这些本地 Skill 的职责是补充仓库特有规则, 而不是重写或覆盖上游通用 Skill

# 方案对比

## 方案 A: 保留现状, 仅局部删减内容

- 优点: 改动小
- 缺点: 仍保留多个知识入口, 上下文膨胀问题没有根治

## 方案 B: 把全部仓库知识拆成很多独立 Skill

- 优点: 领域边界清楚
- 缺点: 触发点变多, Skill 数量膨胀, 不符合“一个主入口 + references 路由”的目标

## 方案 C（当前选中）: 一个规则使用入口 + 一个参考维护入口 + 少量独立流程/工具 Skill

- 优点: 入口清晰, 知识按需读取, 使用与维护分离, 符合 Harness 的 `Tool Wrapper` 思路
- 缺点: 需要重新梳理现有 Skill 边界与文档归属

# 选中方案

## 顶层 Skill 结构

保留或新建以下顶层 Skill：

- `using-rules`
- `reference-sync`
- `project-extension-writing-skills`
- `project-extension-requesting-code-review`
- `mpy-cli-tool`
- `git-workflow`
- `using-git-worktrees`

其中：

- `using-rules` 是仓库规则与领域知识的统一使用入口
- `reference-sync` 是仓库参考文档的统一维护入口
- `project-extension-writing-skills` 是仓库内 Skill 设计、编写和改造的统一本地规范入口, 用于补充 superpowers `writing-skills`
- `project-extension-requesting-code-review` 是仓库内代码评审入口, 用于补充 superpowers `requesting-code-review` 的本地审查标准
- `mpy-cli-tool` 保留独立, 但重构为轻量路由式工具 Skill
- `git-workflow` 与 `using-git-worktrees` 继续保持流程型定位

## 需要整合的旧 Skill

以下 3 个 Skill 不再作为独立知识入口保留：

- `code-standards`
- `control-system`
- `embedded-development`

它们的内容将被拆解后迁入 `using-rules/references/`。

## `using-rules` 的职责

`using-rules/SKILL.md` 只保留：

- 使用时机
- 路由规则
- 强制查询门禁
- 与其他 Skill 的职责边界

其下的 `references/` 承载细分知识文档。

当前建议的参考文档包括：

- `code-style.md`
- `architecture-boundaries.md`
- `memory-budget.md`
- `embedded-workflow.md`
- `hardware-facts.md`
- `vision-semantics.md`
- `control-system.md`
- `protocol.md`

这些 `references/` 应优先以引用页形式指向当前唯一正文, 而不是复制第二份内容。当前唯一正文可能位于 `docs/`, 也可能已迁入对应 Skill。

`using-rules` 只承载实现阶段需要的规则入口, 不承载最终 review 规则。

## `reference-sync` 的职责

`reference-sync` 负责维护整个仓库的参考文档, 包括但不限于：

- 从 GitHub、官方文档或远端网页同步资料
- 清洗外部页面并转换为适合仓库存储和 Agent 查询的 Markdown
- 记录来源、更新时间和清洗策略
- 更新 Skill 内的 `references/` 文档

`remote-spec-to-markdown` 应被视为该 Skill 的一个子流程或能力来源, 而不是继续作为完全独立的知识维护入口。

## `mpy-cli-tool` 的重构方向

`mpy-cli-tool` 继续保留为独立工具 Skill, 但结构收敛为：

- 主 `SKILL.md` 只保留可用命令索引与路由规则
- Agent 根据要解决的问题跳转到具体大文档
- 详细命令说明、参数语义、路径映射、排障说明迁入 `mpy-cli-tool` 自己的参考文档体系

用户明确要求：`mpy-cli-tool` 不需要在主 Skill 中保留完整手册, 只要保留可用命令索引, 再通过 router 引导到大文档即可。

## `project-extension-writing-skills` 的职责

`project-extension-writing-skills` 用于补充 superpowers 自带的 `writing-skills`, 面向本仓库内 Skill 的编写、改造与审查。

它应明确：

- 先继承 `writing-skills` 的通用方法
- 再应用仓库本地的 Harness 设计模式
- 优先根据任务选择 `Tool Wrapper`、`Reviewer`、`Pipeline` 等结构
- 知识型 Skill 优先采用“短 `SKILL.md` + `references/`”
- 高频工具型 Skill 优先采用“命令索引 + 路由到大文档”

`project-extension-writing-skills/references/` 应通过引用页指向 `docs/harness-design-pattern.md`, 保持该文档只有一份正文事实源。

## `project-extension-requesting-code-review` 的职责

`project-extension-requesting-code-review` 用于功能完成后的最终收口评审, 在 superpowers 原版代码评审能力基础上, 增加仓库特有的审查重点。

当前明确的本地评审重点包括：

- 当前功能是否真的满足当前任务或赛题要求
- 当前改动面是否已经收敛到最小, 是否符合最小改动原则
- 当前改动是否能够对完成赛题做出正贡献
- 当前改动的命名、结构和实现风格是否贴合仓库现有代码风格
- 当前改动是否增加 Python / MicroPython 运行时内存占用, 或破坏既有内存预算约束

这些评审重点需要服从仓库的竞赛结果导向：

- review 不以“功能更全”作为默认加分项
- review 不以“抽象更多、结构更漂亮”作为默认加分项
- 对当前竞赛目标没有直接收益的新增能力、额外封装和长期维护负担, 默认都应被质疑
- 若同一目标存在更小、更省内存、更直接的实现路径, 应优先推荐该路径

其中最高优先级的收口问题应固定为 3 条：

1. 当前功能能否满足要求?
2. 当前实现是否满足最小改动?
3. 当前改动是否对完成赛题有正贡献?

若以上任一问题不能明确回答“是”, review 默认不得通过。

它更适合被设计为 `Reviewer` 型 Skill：

- 主 `SKILL.md` 只说明何时触发、如何执行评审、如何输出结果
- 具体评分标准和检查清单放在 `references/` 中

建议的参考文档包括：

- `references/requirement-fit-checklist.md`
- `references/minimal-change-checklist.md`
- `references/competition-value-checklist.md`
- `references/style-consistency-checklist.md`
- `references/memory-impact-checklist.md`

该 Skill 的目标不是替代通用代码评审, 而是把 superpowers 默认能力中缺失的仓库本地审查维度补齐。

它应作为独立 `Reviewer` 型 Skill 存在, 不与 `using-rules` 混合。

若这些评审清单未来也需要人类直接维护与阅读, 应优先保留一份正式正文, 再由 `references/` 引用页指向, 不复制第二份内容。该正文既可以位于 `docs/`, 也可以位于对应 Skill 目录内。

# 建议目录结构

> 说明: 下列结构用于保留当时的信息架构设计语境, 属于历史语境说明; 其中 `mpy-cli` 与 OpenArt 协议的正式正文落点已按后续迁移结果改成当前生效口径。

```text
.agents/skills/
├── using-rules/
│   ├── SKILL.md
│   └── references/
│       ├── code-style.md -> docs/...
│       ├── architecture-boundaries.md -> docs/...
│       ├── memory-budget.md -> docs/...
│       ├── embedded-workflow.md -> docs/...
│       ├── hardware-facts.md -> references/openart-protocol.md
│       ├── vision-semantics.md -> references/openart-protocol.md
│       ├── control-system.md -> docs/...
│       └── protocol.md -> references/openart-protocol.md
├── reference-sync/
│   ├── SKILL.md
│   ├── references/
│   │   ├── source-policy.md
│   │   ├── sync-strategies.md
│   │   ├── quality-checklist.md
│   │   └── traceability-rules.md
│   └── assets/
│       ├── import-template.md
│       └── source-record-template.md
├── project-extension-writing-skills/
│   ├── SKILL.md
│   └── references/
│       ├── harness-design-pattern.md -> docs/harness-design-pattern.md
│       ├── structure-rules.md -> docs/...
│       ├── naming-rules.md -> docs/...
│       └── migration-checklist.md -> docs/...
├── project-extension-requesting-code-review/
│   ├── SKILL.md
│   └── references/
│       ├── minimal-change-checklist.md -> docs/...
│       ├── style-consistency-checklist.md -> docs/...
│       └── memory-impact-checklist.md -> docs/...
├── mpy-cli-tool/
│   ├── SKILL.md
│   └── references/
│       ├── command-index.md -> references/mpy-cli-manual.md
│       ├── cli-reference.md -> references/mpy-cli-manual.md
│       ├── path-mapping.md -> references/mpy-cli-manual.md
│       └── troubleshooting.md -> references/mpy-cli-manual.md
├── git-workflow/
└── using-git-worktrees/
```

# 路由规则草案

## `using-rules`

- 改普通 Python 模块 -> 查 `code-style.md` 与 `architecture-boundaries.md`
- 触及 `TransportCar`、运行时 owner、诊断与装配 -> 追加查 `memory-budget.md`
- 触及板端、驱动、实时循环、HIL -> 查 `embedded-workflow.md`
- 触及引脚、串口、按钮、电平与板级事实 -> 查 `hardware-facts.md`
- 仓库未明确的硬件事实 -> 必须先问用户, 禁止猜测
- 触及视觉对正、`?vision`、状态机语义 -> 查 `vision-semantics.md`
- 触及 PID、运动学、里程计、轨迹与调参 -> 查 `control-system.md`
- 触及协议字段与语义 -> 查 `protocol.md`

进入最终收口评审时, 不再停留在 `using-rules`, 改用 `project-extension-requesting-code-review`。

## `mpy-cli-tool`

- 想知道有哪些命令 -> 查 `command-index.md`
- 想查某个命令的参数和行为 -> 查 `cli-reference.md`
- 想确认 `source_dir` / `device_upload_dir` / `.mpyignore` 语义 -> 查 `path-mapping.md`
- 想排查连接、扫描、部署失败 -> 查 `troubleshooting.md`

# 风险与控制

## 风险 1: 主 Skill 再次长成大手册

- 控制措施: 明确限制主 `SKILL.md` 只写触发、路由、门禁, 详细内容一律下沉

## 风险 2: references 主题划分不合理, Agent 仍难以定位

- 控制措施: 按任务决策点拆文档, 不按历史 Skill 名称机械拆分

## 风险 3: 正式项目文档与 Agent 私有参考混在一起

- 控制措施: 明确哪些文档是 Skill 内 reference, 哪些仍保留为仓库正式文档

## 风险 4: 文档更新流程和日常使用流程串台

- 控制措施: 严格拆分 `using-rules` 与 `reference-sync` 的职责

## 风险 5: 旧 Skill 独有规则在重构中丢失

- 当前仓库里有一批关键约束只写在旧 Skill 中, 并未完整落到 `docs/` 正文
- 若先删旧 Skill 再补文档, 会直接造成规则丢失
- 控制措施: 必须先做“旧 Skill 独有规则盘点”, 再做归位迁移, 最后才允许删除旧 Skill 结构

## 风险 6: references 机械拆分导致重复入口过多

- 若多个 `references` 只是重复指向同一正文, 但没有清晰的使用场景区分, 会制造表面结构, 反而降低可读性
- 控制措施: `references` 只保留真正有独立用途的入口页, 禁止为了凑目录结构机械拆分

# 迁移边界

## 本次重构包含

- 重构 Skill 信息架构
- 重组知识型 Skill 与高频工具型 Skill 的文档承载方式
- 重新定义 `remote-spec-to-markdown` 的归属
- 重新规划 `mpy-cli-tool` 与 `Protocol` 文档归属
- 新增仓库本地的 `project-extension-writing-skills` Skill, 用于补充 superpowers `writing-skills`
- 新增仓库本地的 `project-extension-requesting-code-review` Skill, 用于补充 superpowers `requesting-code-review`
- 明确正文单一维护原则, Skill `references/` 通过引用页指向唯一事实源文档

## 当前 review 结论

当前实现方案 review 不通过。

不通过原因有两条：

1. 原旧 Skill 中存在一批只写在 Skill 本体、没有进入 `docs/developer/` 的仓库规则；当前做法若直接删除旧 Skill，会丢失这些规则。
2. 当前 `references` 设计中存在过多重复入口，多个引用页机械地指向同一正文，但没有证明这些入口在使用时机上真的不同，结构意义不足。

因此，后续修正方向必须调整为：

- 不再继续以“先删旧 Skill、后补规则”为路径
- 先盘点旧 Skill 独有规则
- 再按“实现阶段 / review 阶段 / Skill 编写阶段”重新归位
- 最后才决定哪些旧 Skill 可以彻底删除

## 修正原则

### 原则 A: 规则本体优先于外壳重构

- 先保规则, 后收结构
- 任何旧 Skill 中独有的规则, 在未明确迁移落点前不得删除
- 本次重写的目标是“拆分旧 Skill 内容”, 不是“替换旧 Skill 内容”
- 原旧 Skill 中的约束、门禁、边界和判断口径必须完整保留, 只能重组与拆分, 不能在重写中蒸发
- 任一旧 Skill 规则若在新结构里没有明确映射落点, 就不得删除对应旧内容
- 若重写导致仓库原有工程约束、性能约束或比赛能力约束弱化, 则该重写视为失败

### 原则 A-1: 只做重构, 不做重写

- 后续对 Skill 与外部正文的处理属于重构, 不是重写
- 重构只允许做：重排结构、拆分章节、调整归属、改进入口关系、增强可路由性
- 重构不允许做：重新发明规则、用新表述替换旧信息、为了整洁删除原有约束、把旧内容压缩到失真
- 若外部正文结构不好, 应先重构其章节与组织方式, 再让 Skill 去引用
- 无论是 Skill 内部文件还是外部正文, 重构完成后都必须能逐条对照原信息, 确认信息没有丢失

### 原则 B: `using-rules` 与 review Skill 按使用时机拆分

- `using-rules` 只承载写代码前和写代码过程中需要主动查询的规则
- `project-extension-requesting-code-review` 只承载代码写完后、请求 review 时需要的检查标准
- 不把所有 rules 机械搬进 `using-rules` 一个目录下

### 原则 C: 引用页必须有明确场景差异

- 只有当同一正文在不同使用阶段确实需要不同入口时, 才允许拆成多个引用页
- 若多个引用页只是换了文件名, 但都让 Agent 去读同一正文且没有不同的进入理由, 就应合并

## 下一步设计任务

在继续实现前, 必须先完成以下设计动作：

1. 盘点旧 `code-standards`、`embedded-development`、`control-system` 中只存在于 Skill 本体的规则
2. 标记这些规则分别属于：
   - 实现阶段规则
   - 完工 review 规则
   - Skill 编写规范
3. 审查当前全部 `references` 是否存在重复入口, 合并没有独立意义的引用页
4. 在规则迁移表完成前, 不再把“删除旧 Skill”视为完成条件

# 旧 Skill 规则迁移清单

本节用于盘点旧 Skill 中只存在于 Skill 本体、尚未被当前 `docs/` 正文完整覆盖的关键规则。

这些规则必须先归位, 再允许继续调整 Skill 外壳结构。

## 旧 `code-standards` 独有规则

### 实现阶段规则（应迁入 `using-rules`）

- 目标平台是 RT1021 + MicroPython, 本地开发兼容 Python 3.8+
- 运行时代码默认不要依赖 `typing`, 若必须使用类型辅助, 要采用不影响板端导入的写法
- 注释和文档字符串统一使用中文
- 文档注释统一采用 Doxygen 风格, 默认使用 `@brief`, 按需补充 `@param`、`@return`、`@note`、`@warning`
- 注释中的标点统一使用半角符号, 且标点后加空格
- 单行注释行尾不加句号、逗号、分号、冒号等收尾标点
- 对复杂流程、状态机分支、lazy 装配、兼容桥接和非显然控制逻辑, 必须补中文块注释
- 函数、类和模块必须有中文 Doxygen 文档注释, 说明输入、输出、副作用和关键约束
- 行数门禁按非注释代码行计算, 注释和空行不计入
- 一个领域拆成 2 个以上实现文件时, 必须优先改为包目录加 `__init__.py`
- 禁止使用共同前缀平铺文件模拟命名空间
- 魔法数字集中到 `config/params.py`
- 禁止静默失败, 只捕获预期异常并保留上下文

### 架构边界规则（应迁入 `using-rules`）

- `hardware` 只放硬件驱动与总线访问, 不放业务逻辑
- `control` 只放 PID、运动学、轨迹、姿态估计等控制算法
- `filters` 只放独立可复用滤波算法
- `services` 只做编排, 不承载底层算法、设备访问细节或隐藏状态机
- `vision` 或独立领域包只放视觉协议、状态机和领域转换逻辑, 不混入服务编排
- `storage` 只负责持久化
- `config` 只负责配置与常量
- `utils` 只放通用纯函数工具
- 依赖方向必须保持单向, 禁止下层反向依赖上层, 禁止循环依赖与跨层跳跃调用
- 一个运行时状态只能有一个主拥有者
- 模块协作必须通过显式接口、受控数据结构或明确协议完成
- command handler、query handler、facade、adapter 不得直接读写宿主内部字段或临时属性
- import-time 自动注册必须 fail-fast、可观测、可验证
- diagnostics 只能只读聚合 owner 状态, 不得缓存第二份运行时状态
- command / query 装配默认应显式延迟加载, 不得回退到 import-time 全量注册

### 性能与最小实现规则（实现阶段 + review 阶段都要保留）

- 对 `TransportCar`、运行时 owner、诊断 facade、命令装配和板端 probe 的改动, 首要目标是最小内存占用指标
- 新增常驻对象必须说明 owner、阶段、A / B / C / D / E 分类、触发条件和必要性
- import-time 禁止目录扫描、自动发现、自动注册和重型单例初始化
- 模块级可变运行时全局状态属于阻断项
- 可延迟功能若被重新放回构造期无条件初始化, 直接不通过
- 热路径新增大字符串拼接、大临时容器或无解释动态分配时, 必须给出必要性证明
- 结构更清晰但内存指标未改善, 不算有效重构
- 没有 2 个以上真实消费者时, 不要引入通用框架式抽象
- 不要为未来假设需求提前引入事件总线、插件系统或多层适配器链
- 若新增抽象只是搬运复杂度, 但没有降低理解成本或测试成本, 视为过度设计

### review 阶段规则（应迁入 `project-extension-requesting-code-review`）

- 代码是否位于正确分层目录
- 是否存在上层反向依赖或循环依赖
- 是否满足类型提示、中文文档和异常处理要求
- 是否将参数和阈值集中到 `config/params.py`
- 是否满足 5ms 控制周期下的性能约束
- 是否存在状态单一所有权不明、状态双写或状态泄漏
- 是否通过私有字段、临时属性或隐式上下文协议耦合多个模块
- 是否为了未来假设需求引入没有现实收益的抽象
- 是否把算法细节、设备细节或领域状态继续堆进编排层
- 是否把 import-time 副作用当作默认装配方式, 且缺少失败可观测性
- 是否给出了 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle` 和 `diag_survival` 证据
- 是否说明了新增常驻对象为什么属于 A / B 类, 而不是 C / D 类
- review 输出不能停留在“风格还可以”这种表面结论, 必须明确职责边界、状态归属、耦合方式和抽象成本是否健康

## 旧 `embedded-development` 独有规则

### 实现阶段规则（应迁入 `using-rules`）

- 行为改动必须先选测试层：`unit` / `contract` / `HIL`
- 行为改动必须先有失败测试, 主机侧通过只是起点, 不是终点
- `tests/unit` 用于纯逻辑、确定性算法、解析器、路由、存储、工具函数
- `tests/contract` 用于命令处理器、协议路由、副作用契约
- `tests/hil` 是真实设备、真实时序、真实外设、真实控制循环的最终留证层
- 进入设备路径的判据包括：修改 `src/hardware/`、修改 `src/services/transport_car.py`、依赖真实串口/编码器/IMU/电机/ticker、需要证明 5ms 预算或真实动作链路
- `stage2` 只做 MPY smoke, 不验证真实硬件动作
- `stage3` 通过 `uart3` 做人工观测和故障归因, 不是自动 PASS / FAIL
- `HIL` 必须留下步骤、预期、实际输出和 PASS / FAIL 结论

### 硬件与实时性护栏（应迁入 `using-rules`）

- 每个外设一个独立模块, 接口最小化, 业务编排放 `services`
- 驱动层不夹带业务逻辑
- 已知 `src/boot.py` 的 Button 1-4 引脚分别是 `C8`、`C9`、`C14`、`C15`
- 已知 `src/boot.py` 的 D8/D9 带上拉, `1` 表示开关关闭, `0` 表示开关闭合
- 任何仓库或用户未明确给出的硬件引脚、接线、板级资源映射都必须先问用户, 禁止猜测
- 串口处理默认非阻塞
- PWM、方向切换与占空比限幅要原子化处理
- 中断回调只置标志, 不执行重计算或阻塞 I/O
- 关键路径避免动态分配和大字符串操作
- 新增逻辑必须评估耗时, 建议用 `ticks_us` 量测
- 控制周期超预算时, 先降复杂度, 再讨论新特性
- 电机方向、编码器方向与运动学坐标系必须一致
- IMU 设备 ID、零漂校准文件和读数稳定性必须可验证

### 视觉语义与联调规则（应迁入 `using-rules`）

- 视觉对正语义必须以 `references/openart-protocol.md`、`src/services/vision_protocol.py`、`src/services/vision_state_machine.py` 为准
- 若看到 `src/control/kinematics.py` 中旧注释, 视为历史残留, 不得拿来推断当前协议方向
- 车体系方向固定为 `y+` 前进、`x+` 右移、`omega+` / `d_angle+` 顺时针
- `dx/dy/d_angle` 是车体系相对增量, `x/y/angle` 是世界系绝对目标
- 视觉输入只认 `UART6` 上完整框 `left/top/right/bottom`
- OpenArt 传入的 `left/top/right/bottom` 已经是最终画面坐标, 主控侧不得再次翻转
- `ALIGN_ANGLE`、`ALIGN_DIST`、`ALIGN_DX`、`ORBITING`、`PUSHING`、`RETURNING` 的符号关系和解释口径必须保持一致
- 没有 HIL 证据前, 不得把 `push_angle_deg = -90` 口头改写为绝对物理方向
- 任何“左 / 右 / 前 / 后 / 顺时针 / 逆时针”描述都必须带参考系
- `uart3` 观测或 `tests/hil/` 留证前, 必须先验证完整框、`obs_center_x`、`obs_bottom`、阶段顺序和 `UART6` 上旧 `x,y` 的吞掉行为

### review / 验证阶段规则（应迁入 `project-extension-requesting-code-review`）

- 不允许“先把代码写完再补测试”
- 不允许“主机测试过了, 就不用上板了”
- 不允许“直接让车动一下看看”替代设备门禁流程
- 不允许跳过 `stage2` 直接看 `stage3`
- 不允许“看到串口有输出就算完成”
- 不允许“HIL 以后再补”
- 进入设备路径后, 交付物必须包含主机测试、设备命令、smoke 输出、观测输出、失败归因和 HIL 证据

## 旧 `control-system` 独有规则

### 实现阶段规则（应迁入 `using-rules`）

- 控制层级固定为位置环 -> 速度环 -> PWM 输出
- 反馈来源固定为编码器 + IMU
- 控制模式包括速度模式、位置模式、角度保持模式
- 改算法前必须先确认编码器方向、电机方向和 IMU 校准等硬件基线
- 参数辨识先行, 使用 `pid_identify.py` 生成最新电机参数
- 关键参数统一在 `config/params.py`, 禁止散落阈值
- 控制相关跨模块改动必须保持 `services` 只做编排, 算法实现留在 `control` 和 `filters`
- 控制周期预算默认 5ms, 新增计算必须评估耗时

### 调参与诊断规则（应迁入 `using-rules`）

- 调参顺序固定为：校准陀螺仪 -> 重新辨识电机 -> 只开速度环调内环 -> 打开位置环调外环 -> 调航向保持 -> 做组合轨迹联调
- 振荡时先降 P, 再增 D, 检查滤波与周期抖动
- 响应慢时增 P、减滤波延迟、核对前馈
- 稳态误差时补 I 或校正前馈, 并复核辨识参数
- 航向漂移时重做 IMU 零漂, 检查积分与 `dt`
- 轨迹偏差时检查打滑、最大速度、加速度限制

### review / 验证阶段规则（应迁入 `project-extension-requesting-code-review`）

- 单轮和三轮协同控制都必须通过
- 速度模式、位置模式、模式切换都必须通过
- `?lock` 相关行为必须与相对位移命令一致
- 长时间运行不得出现明显航向漂移失控
- 交付物必须包含控制算法或参数变更说明、调参与验证记录, 必要时补充回归测试脚本或验证命令

## 当前迁移设计约束

基于以上清单, 后续重写必须满足：

1. 旧 `code-standards`、`embedded-development`、`control-system` 中的独有规则先逐条安置, 再讨论删除旧结构
2. `using-rules` 只接实现阶段规则, 不再混入 review 规则
3. `project-extension-requesting-code-review` 只接完工后的 review 标准
4. 若同一正文不足以承载旧 Skill 独有规则, 必须先补正式正文, 不得直接让规则蒸发

## 本次重构暂不包含

- 立即实现所有自动同步脚本或定时更新机制
- 修改 superpowers 自带 Skill
- 改变 `git-workflow` 与 `using-git-worktrees` 的核心职责

# 已确定结论

1. 仓库知识主入口保留为 `using-rules`, 不再继续改名。
2. `harness-design-pattern` 仍保留在 `docs/` 作为正式正文; `mpy-cli` 与 OpenArt 协议正文已分别迁入 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` 与 `.agents/skills/using-rules/references/openart-protocol.md`, Skill 侧继续通过 `references/` 路由进入。
3. `remote-spec-to-markdown` 不再作为独立 Skill 保留, 其职责直接收敛进 `reference-sync`。
4. `code-standards`、`control-system`、`embedded-development` 与 `remote-spec-to-markdown` 作为已废弃 Skill 直接删除, 不保留兼容层或重定向入口。
5. 扩展 superpowers 的本地 Skill 使用 `project-extension-` 前缀, 当前落地为 `project-extension-writing-skills` 与 `project-extension-requesting-code-review`。
6. `project-extension-writing-skills` 与 `project-extension-requesting-code-review` 的 `description` 沿用 superpowers 原语义, 不采用同名覆盖方案。

# 待后续细化问题

1. `reference-sync` 后续是否只做人触发的半自动更新, 还是允许在特定场景下做主动检查与提议更新。
2. `project-extension-requesting-code-review` 的触发范围是否只针对代码改动, 还是对所有可提交改动统一触发, 但代码改动时额外增加内存评审。
3. 哪些现有 `docs/` 文档最终应继续长期保留为正式正文, 哪些可以在未来收敛为更明显的 Skill 私有资产。
