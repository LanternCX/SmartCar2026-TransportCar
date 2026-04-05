# Skill 文档归属调整旧引用盘点清单

## 当前状态

- 本清单已收口，原先位于根 `docs/` 的两份旧正文路径都已删除。
- 当前正式落点：
  - `mpy-cli` 正式手册：`.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
  - OpenArt 协议正文：`.agents/skills/using-rules/references/openart-protocol.md`
- 本清单保留迁移记录，但不再把旧根路径当作活动引用。
- `2026-03-23-skill-information-architecture-design.md` 与 `2026-03-23-skill-information-architecture.md` 已补充“历史语境 / 当前口径”说明，与本清单状态一致。

## 处理策略说明

- `立即改写`：正文或入口已直接改到当前 Skill 路径。
- `保留原语境并补迁移说明`：保留原方案或归档语境，同时把事实源说明改成当前正式落点。
- `需要同步更新测试`：仅替换事实源路径，保持测试意图不变。

## 收口清单

| 路径 | 历史对象 | 处理策略 | 当前落点 | 收口状态 |
| --- | --- | --- | --- | --- |
| `.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md` | 根 `docs/` 下旧 mpy-cli 正文 | 立即改写 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `.agents/skills/mpy-cli-tool/references/troubleshooting.md` | 根 `docs/` 下旧 mpy-cli 正文 | 立即改写 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `.agents/skills/using-rules/references/hardware-and-protocol.md` | 根 `docs/` 下旧 OpenArt 协议正文 | 立即改写 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `tests/unit/services/test_transport_car_logging.py` | 根 `docs/` 下旧 OpenArt 协议正文 | 需要同步更新测试 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md` | 旧协议正文、旧 mpy-cli 正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md`；`.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `docs/superpowers/specs/2026-03-23-skill-information-architecture-review-fixes-design.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/specs/2026-03-14-physical-camera-id-overlap-design.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/specs/2026-03-12-transport-runtime-decoupling-design.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/specs/2026-03-13-dual-camera-single-state-machine-design.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/specs/2026-03-09-mpy-cli-skill-design.md` | 旧 mpy-cli 正文 | 保留原语境并补迁移说明 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `docs/superpowers/plans/2026-03-23-skill-information-architecture.md` | 旧协议正文、旧 mpy-cli 正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md`；`.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `docs/superpowers/plans/2026-03-14-physical-camera-id-overlap.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/plans/2026-03-13-dual-camera-single-state-machine.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/plans/2026-03-10-global-log-system.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/plans/2026-03-09-vision-bbox-observation.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/plans/2026-03-09-mpy-cli-skill-implementation.md` | 旧 mpy-cli 正文 | 保留原语境并补迁移说明 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `docs/superpowers/memory/milestone/entries/2026-03/2026-03-09-1.md` | 旧 mpy-cli 正文 | 保留原语境并补迁移说明 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md` | 旧协议正文 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md` | 已完成 |
| `docs/superpowers/plans/2026-03-24-skill-document-ownership.md` | 本轮迁移计划中的旧根路径描述 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md`；`.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |
| `docs/superpowers/specs/2026-03-24-skill-document-ownership-design.md` | 本轮迁移设计中的旧根路径描述 | 保留原语境并补迁移说明 | `.agents/skills/using-rules/references/openart-protocol.md`；`.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | 已完成 |

## 覆盖类别

- 测试对象：`tests/unit/services/test_transport_car_logging.py`
- Skill 引用页：`.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`、`.agents/skills/mpy-cli-tool/references/troubleshooting.md`、`.agents/skills/using-rules/references/hardware-and-protocol.md`
- 历史文档：以上 `docs/superpowers/specs/`、`docs/superpowers/plans/`、`docs/superpowers/memory/` 条目

## `reference-sync` 持续维护对象

| 文档对象 | 当前正式落点 | 当前作用 | 后续维护要求 |
| --- | --- | --- | --- |
| 题面使用说明 | `docs/problem_statement/README.md` | 说明阅读顺序、使用方式、维护原则 | 保持为 `reference-sync` 持续维护对象，并在 checklist 中列出 |
| 题面来源与追溯 | `docs/problem_statement/sources.md` | 记录外部来源、本地产物映射、清洗策略、更新建议 | 保持为 `reference-sync` 核心维护对象，并在 registry 中列出 |
| 题面规格正文 | `docs/problem_statement/spec.md` | 题面规则事实源与 REQ 编号索引 | 更新官方规则时同步复核 |
| 题面问答正文 | `docs/problem_statement/qa.md` | 规则澄清与问答事实源 | 新增问答后同步复核 |
| `mpy-cli` 正式手册 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | `mpy-cli` 统一正式正文 | 变更命令、参数、路径边界或排障策略时同步检查 registry 与 checklist |
| OpenArt 协议正文 | `.agents/skills/using-rules/references/openart-protocol.md` | 协议与硬件/视觉链路事实源 | 变更协议字段、链路约定、示例或兼容规则时同步检查 registry 与 checklist |

## 收口结论

- 计划明确列出的文件均已处理完成。
- 三类对象（测试、Skill 引用页、历史文档）都已纳入并收口。
- 本清单现在反映的是迁移后的稳定状态，可直接用于后续复核。
