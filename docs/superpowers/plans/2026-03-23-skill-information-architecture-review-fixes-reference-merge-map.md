# Skill 引用页并表清单

> 当前文件记录本次信息架构修正后的完整并表映射, 用于最终结构验收。

## 使用模板

- 固定字段：`旧页`、`新页`
- 固定写法：`旧页 -> 新页`
- 后续补其他 Skill 时，先补表格，再补一行简短说明即可，不重复写两份映射内容

## using-rules

| 旧页 | 新页 |
| --- | --- |
| `code-style.md` | `implementation-rules.md` |
| `architecture-boundaries.md` | `implementation-rules.md` |
| `memory-budget.md` | `implementation-rules.md` |
| `embedded-workflow.md` | `implementation-rules.md` |
| `hardware-facts.md` | `hardware-and-protocol.md` |
| `vision-semantics.md` | `hardware-and-protocol.md` |
| `control-system.md` | `strategy-and-control.md` |
| `protocol.md` | `hardware-and-protocol.md` |

- 说明：`code-style.md -> implementation-rules.md`，其余实现约束同并；硬件、视觉与协议统一并入 `hardware-and-protocol.md`，比赛目标与控制语义并入 `strategy-and-control.md`

## project-extension-requesting-code-review

| 旧页 | 新页 |
| --- | --- |
| `requirement-fit-checklist.md` | `review-gates.md` |
| `minimal-change-checklist.md` | `review-gates.md` |
| `competition-value-checklist.md` | `review-gates.md` |
| `style-consistency-checklist.md` | `review-gates.md` |
| `memory-impact-checklist.md` | `ai-memory-review.md` |

- 说明：`requirement-fit-checklist.md -> review-gates.md`，其余收口门禁统一并入 `review-gates.md`；内存量化检查独立保留在 `ai-memory-review.md`

## project-extension-writing-skills

| 旧页 | 新页 |
| --- | --- |
| `harness-design-pattern.md` | `writing-rules.md` |
| `structure-rules.md` | `writing-rules.md` |
| `naming-rules.md` | `writing-rules.md` |
| `migration-checklist.md` | `migration-checklist.md` |

- 说明：`harness-design-pattern.md -> writing-rules.md`，结构与命名规则统一并入 `writing-rules.md`；迁移检查仍保留独立页

## mpy-cli-tool

| 旧页 | 新页 |
| --- | --- |
| `command-index.md` | `command-and-path-boundaries.md` |
| `cli-reference.md` | `command-and-path-boundaries.md` |
| `path-mapping.md` | `command-and-path-boundaries.md` |
| `troubleshooting.md` | `troubleshooting.md` |

- 说明：`command-index.md -> command-and-path-boundaries.md`，其余命令与路径说明按同一模式合并；排障仍保留独立页

## reference-sync

| 旧页 | 新页 |
| --- | --- |
| `source-policy.md` | `source-and-quality.md` |
| `sync-strategies.md` | `sync-rules.md` |
| `quality-checklist.md` | `source-and-quality.md` |
| `traceability-rules.md` | `source-and-quality.md` |

- 说明：`sync-strategies.md -> sync-rules.md`；其余来源、追溯与质量检查页统一并入 `source-and-quality.md`
