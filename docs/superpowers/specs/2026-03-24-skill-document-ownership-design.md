---
title: Skill 文档归属与维护边界调整设计
date: 2026-03-24
status: approved
scope: .agents/skills, 根 docs 下旧 OpenArt 协议正文, 根 docs 下旧 mpy-cli 正文
---

# 背景

当前仓库里的 Skill 文档归属仍有三处不一致：

1. `mpy-cli-tool` 已经是独立工具入口，但完整正文仍留在根 `docs/`。
2. OpenArt 通信协议仍放在根 `docs/` 下旧 OpenArt 协议正文里，没有进入 Skill 体系。
3. `reference-sync` 只表达了“正文在 docs”，但没有把“来源记录”“维护位置”“维护清单”拆清楚。

用户本次明确提出的新要求是：

- `mpy-cli-tool` 应包含 `mpy-cli` 的完整文档。
- OpenArt 通信协议应写入 Skill，根 `docs/` 下旧 OpenArt 协议正文不再留在 `docs/` 下。
- `reference-sync` 应包含各文档的来源和落点，但正式正文中不应混入来源说明。
- `reference-sync` 需要维护所有需要持续同步/核对的文档 checklist，其中必须包含 `mpy-cli` 文档。

# 用户确认的设计结论

本次讨论后，用户确认采用以下归属原则：

1. 正式正文优先跟随对应 Skill，而不是继续集中留在根 `docs/`。
2. `reference-sync` 只负责维护信息，不承载正式正文。
3. 协议正文不新建独立 Skill，而是并入 `using-rules` 体系。

# 设计目标

1. 让 `mpy-cli-tool` 成为自洽的完整工具文档入口。
2. 让 OpenArt 协议进入 `using-rules` 领域，不再漂浮在根 `docs/`。
3. 把“正式正文”和“来源追溯/维护清单”彻底分离。
4. 让后续文档维护时能一眼看到需要同步哪些文档、各自来源是什么、当前应该维护在哪里。

# 设计原则

## 原则 1：正式正文跟随 Skill 归属

- 工具型正文跟随工具 Skill。
- 规则与协议型正文跟随规则 Skill。
- 根 `docs/` 不再继续承接这类 Skill 私有正文。

## 原则 2：正式内容与来源记录分离

- 正式正文只写可直接使用的说明、规则、协议和边界。
- 来源链接、抓取位置、同步依据、维护动作统一写入 `reference-sync`。
- 任何正式正文都不再夹带“本文来源于哪里”的维护信息。

## 原则 3：入口短、引用清楚、正文完整

- `SKILL.md` 仍保持短入口和路由职责。
- 正式正文直接落在 Skill 自己的 `references/` 中，不新增 `docs/` 等新目录层次。
- 真正需要反复查阅的完整说明必须在 Skill 体系内可直接到达。

# 方案对比

## 方案 A：只移动文件位置

- 优点：改动最小。
- 缺点：`reference-sync` 的来源记录与 checklist 问题仍未解决。

## 方案 B：继续把正文统一留在 `docs/`

- 优点：集中。
- 缺点：与用户刚确认的“正文跟 Skill 走”相冲突。

## 方案 C（选中）：Skill 持有正式正文，`reference-sync` 单独维护来源与 checklist

- 优点：归属清晰，维护职责单一，后续同步更不容易混乱。
- 缺点：需要重写部分引用关系与目录说明。

# 选中方案

## `mpy-cli-tool`

- 保留短入口 `SKILL.md`。
- 在 `mpy-cli-tool/references/mpy-cli-manual.md` 放置完整正式正文。
- `references/command-and-path-boundaries.md` 与 `references/troubleshooting.md` 继续作为轻量入口页，并明确指向 `references/mpy-cli-manual.md` 的对应章节。
- 根 `docs/` 下旧 mpy-cli 正文不再保留为正式入口；迁移完成后删除该文件，并把仓库内旧引用统一改到 Skill 路径。

## `using-rules`

- 把 OpenArt 通信协议并入 `using-rules` 管辖范围。
- 在 `using-rules/references/openart-protocol.md` 放置协议完整正式正文。
- `using-rules/references/hardware-and-protocol.md` 保留为总入口页，但要改为把协议事实明确路由到 `references/openart-protocol.md`。
- 根 `docs/` 下旧 OpenArt 协议正文从根 `docs/` 删除，不再保留跳转页或副本。

## `reference-sync`

- 明确区分“正式正文”与“维护记录”。
- Skill 内新增两份明确维护文档：
  - `references/source-registry.md`：记录文档来源与正式落点
  - `references/maintenance-checklist.md`：记录维护 checklist
- checklist 至少覆盖：
  - `mpy-cli` 完整文档
  - OpenArt 通信协议文档
  - 当前仓库中其他仍需持续同步或人工核对的参考文档
- 每个 checklist 项需要能回答三件事：来源在哪里、正式正文在哪里、维护时需要检查什么。

## 明确目标路径

本次调整后，目标文件路径固定为：

- `mpy-cli` 正式正文：`.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- `mpy-cli` 入口页：`.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`
- `mpy-cli` 排障页：`.agents/skills/mpy-cli-tool/references/troubleshooting.md`
- OpenArt 协议正式正文：`.agents/skills/using-rules/references/openart-protocol.md`
- 协议总入口页：`.agents/skills/using-rules/references/hardware-and-protocol.md`
- 来源与落点记录：`.agents/skills/reference-sync/references/source-registry.md`
- 文档维护 checklist：`.agents/skills/reference-sync/references/maintenance-checklist.md`

# 目录与信息流

建议落点如下：

- `mpy-cli-tool/`
  - `SKILL.md`
  - `references/mpy-cli-manual.md`
  - `references/command-and-path-boundaries.md`
  - `references/troubleshooting.md`
- `using-rules/`
  - `SKILL.md`
  - `references/openart-protocol.md`
  - `references/hardware-and-protocol.md`
- `reference-sync/`
  - `SKILL.md`
  - `references/source-registry.md`
  - `references/maintenance-checklist.md`
  - `assets/*.md`

信息流统一为：

1. Agent 命中 `SKILL.md`。
2. 按 `references/` 进入对应主题入口。
3. 再进入该 Skill 自己持有的正式正文。
4. 若要更新正文，再转到 `reference-sync` 查看来源与 checklist。

# 错误处理与维护边界

- 若发现正式正文与来源记录不一致，以正式正文当前落点为运行事实源，并在 `reference-sync` 中补齐维护记录。
- 若发现某份正式正文没有来源记录，不在正文内补来源说明，而是在 `reference-sync` 增补该条目。
- 若后续新增需要长期维护的参考文档，必须同步补入 `reference-sync` checklist，否则视为信息架构不完整。
- 任何旧路径引用若仍指向根 `docs/` 下旧 mpy-cli 正文或根 `docs/` 下旧 OpenArt 协议正文，都视为迁移未完成。

# 验证方式

完成落地后应能验证：

1. 从 `.agents/skills/mpy-cli-tool/SKILL.md` 可以走到 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`。
2. 从 `.agents/skills/using-rules/SKILL.md` 可以走到 `.agents/skills/using-rules/references/openart-protocol.md`。
3. 根 `docs/` 下不再保留旧 OpenArt 协议正文和旧 mpy-cli 正文。
4. `.agents/skills/reference-sync/references/maintenance-checklist.md` 中明确存在 `mpy-cli` 与 OpenArt 协议两个条目。
5. `.agents/skills/reference-sync/references/source-registry.md` 中可以直接看到这两份文档的来源与正式落点。
6. 仓库内旧引用不再指向根 `docs/` 下旧 OpenArt 协议正文或旧 mpy-cli 正文。
7. `mpy-cli` 正式正文和 OpenArt 协议正文中不再出现来源追溯类维护文字。

# 实施顺序

1. 为 `mpy-cli-tool` 准备 Skill 内正式正文，并重写引用入口。
2. 迁移 OpenArt 协议正文到 `using-rules`，更新协议入口引用。
3. 重写 `reference-sync`，补齐来源记录与维护 checklist。
4. 清理旧路径，确保根 `docs/` 不再保留旧 OpenArt 协议正文、旧 mpy-cli 正文，并收口所有旧引用。
