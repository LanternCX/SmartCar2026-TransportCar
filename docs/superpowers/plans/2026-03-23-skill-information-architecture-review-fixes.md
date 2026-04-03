# Skill 信息架构评审修正实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 追回被删除旧 Skill 的完整规则，把用户不需要人工 review 的正文迁入 Skill 私有体系，并收缩重复路由。

**Architecture:** 先把 Git 历史中的旧 Skill 内容恢复成规则盘点依据，再按“实现阶段 / AI 收口自检 / Skill 编写规范”三类重新归位。随后收缩 `docs/developer/` 到仅保留 `strategy.md` 与 `tasks.md`，最后合并高重复率引用页并完成结构验证。

**Tech Stack:** Markdown, Git 历史检索, 仓库本地 Skill 文档, Python 校验脚本, grep 内容检查

---

### Task 1: 从 Git 历史追回旧 Skill 规则基线

**Files:**
- Verify: `.agents/skills/code-standards/SKILL.md`（Git 历史）
- Verify: `.agents/skills/embedded-development/SKILL.md`（Git 历史）
- Verify: `.agents/skills/control-system/SKILL.md`（Git 历史）
- Create: `docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md`

- [ ] **Step 1: 从 Git 历史读取 3 个旧 Skill 的最后有效版本**

Run: `git log --format='%H %s' -- .agents/skills/code-standards/SKILL.md .agents/skills/embedded-development/SKILL.md .agents/skills/control-system/SKILL.md`

Expected: 输出包含删除前相关提交，能够定位每个旧 Skill 的最后有效版本

- [ ] **Step 2: 对每个旧 Skill 导出最后有效正文用于人工比对**

Run: `git show <commit>:.agents/skills/code-standards/SKILL.md && git show <commit>:.agents/skills/embedded-development/SKILL.md && git show <commit>:.agents/skills/control-system/SKILL.md`

Expected: 能完整看到 3 个旧 Skill 的删除前正文

- [ ] **Step 3: 对照新 spec，把仅存在于旧 Skill 或表述更完整的规则补进迁移表**

Create: `docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md`

要求该清单至少包含 4 列：
- 原 Skill
- 原规则原文
- 新归属 Skill / 正文
- 迁移状态

要求迁移状态最终统一收口为：`待迁移` / `已完成`
要求每一条旧规则都拆成独立表格行，禁止把多条规则合并成一行概括记录

- [ ] **Step 4: 运行规则追回完整性检查**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md').read_text()
for needle in [
    '目标平台是 RT1021 + MicroPython',
    '行为改动必须先选测试层',
    '控制层级固定为位置环 -> 速度环 -> PWM 输出',
    '新归属 Skill / 正文',
]:
    assert needle in text, needle
print('history rule recovery baseline ready')
PY`

Expected: `history rule recovery baseline ready`

- [ ] **Step 5: 在规则盘点清单中逐条标记新归属落点，不允许留空**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md').read_text()
assert '| 原 Skill | 原规则原文 | 新归属 Skill / 正文 | 迁移状态 |' in text
assert '|| 已完成 |' not in text
assert '| code-standards |' in text
assert '| embedded-development |' in text
assert '| control-system |' in text
print('rule inventory destinations assigned')
PY`

Expected: `rule inventory destinations assigned`

### Task 2: 收缩 `docs/developer/` 到用户人工 review 最小面

**Files:**
- Modify: `.agents/skills/using-rules/SKILL.md`
- Modify or Create: `.agents/skills/using-rules/references/*.md`
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Delete or Move: `docs/developer/memory-review.md`
- Delete or Move: `docs/developer/transportcar-memory-assets.md`
- Delete or Move: `docs/developer/tdd-workflow.md`

- [ ] **Step 1: 先完成 `using-rules` 的最终分组与实现阶段承接范围**

建议最终分组：
- `implementation-rules.md`
- `hardware-and-protocol.md`
- `strategy-and-control.md`

- [ ] **Step 2: 把旧 Skill 的实现阶段规则与 `docs/developer` 中要迁出的执行型内容一起归入上述分组**

Modify:
- `.agents/skills/using-rules/references/implementation-rules.md`
- `.agents/skills/using-rules/references/hardware-and-protocol.md`
- `.agents/skills/using-rules/references/strategy-and-control.md`

- [ ] **Step 3: 明确 `strategy.md` 与 `tasks.md` 是否还包含不该让用户 review 的执行型内容**

Run: `python3 - <<'PY'
from pathlib import Path
for path in ['docs/developer/strategy.md', 'docs/developer/tasks.md']:
    text = Path(path).read_text()
    print(path, len(text.splitlines()))
PY`

Expected: 输出两个保留正文的当前行数，用于后续确认未错误删除主目标信息

- [ ] **Step 4: 把 memory / TDD 正文迁入 Skill 私有体系，不再留在 `docs/developer/`**

Modify or Create:
- `.agents/skills/project-extension-requesting-code-review/SKILL.md`
- `.agents/skills/project-extension-requesting-code-review/references/ai-memory-review.md`

- [ ] **Step 5: 先确认迁出的内容已经在新归属中落位，再删除 `docs/developer/` 中旧正文**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md').read_text()
assert '待迁移' not in text, '仍有规则未归位，禁止先删旧正文'
print('rule migration completed before developer-doc deletion')
PY`

Expected: `rule migration completed before developer-doc deletion`

- [ ] **Step 6: 删除或迁空 `docs/developer/` 中不再给用户 review 的 3 份正文**

Run: `python3 - <<'PY'
from pathlib import Path
remaining = sorted(p.name for p in Path('docs/developer').glob('*.md'))
print(remaining)
PY`

Expected: 最终只剩 `['strategy.md', 'tasks.md']`

- [ ] **Step 7: 验证用户人工 review 面已收缩完成**

Run: `python3 - <<'PY'
from pathlib import Path
remaining = {p.name for p in Path('docs/developer').glob('*.md')}
assert remaining == {'strategy.md', 'tasks.md'}, remaining
print('developer docs narrowed')
PY`

Expected: `developer docs narrowed`

### Task 3: 重新归位 AI 收口与 memory 自检规则到 `project-extension-requesting-code-review`

**Files:**
- Modify: `.agents/skills/project-extension-requesting-code-review/SKILL.md`
- Modify or Create: `.agents/skills/project-extension-requesting-code-review/references/*.md`
- Delete or Merge: `.agents/skills/project-extension-requesting-code-review/references/requirement-fit-checklist.md`
- Delete or Merge: `.agents/skills/project-extension-requesting-code-review/references/minimal-change-checklist.md`
- Delete or Merge: `.agents/skills/project-extension-requesting-code-review/references/competition-value-checklist.md`
- Delete or Merge: `.agents/skills/project-extension-requesting-code-review/references/style-consistency-checklist.md`
- Delete or Merge: `.agents/skills/project-extension-requesting-code-review/references/memory-impact-checklist.md`

- [ ] **Step 1: 把 review 入口压成最少的检查面**

建议最终分组：
- `review-gates.md`
- `ai-memory-review.md`

- [ ] **Step 2: 将旧 Skill 中所有收口规则逐条迁入上述两组**

必须覆盖：
- 满足要求
- 最小改动
- 正贡献
- 风格一致性
- memory 量化检查
- 板端验证与 HIL 留证要求

- [ ] **Step 3: 在主 Skill 中明确“memory 默认由 AI 执行，不交给用户人工评估”**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('.agents/skills/project-extension-requesting-code-review/SKILL.md').read_text()
for needle in ['满足要求', '最小改动', '正贡献', 'AI', '内存']:
    assert needle in text, needle
print('project review routing updated')
PY`

Expected: `project review routing updated`

- [ ] **Step 4: 验证 review 引用页数量已收缩**

Run: `python3 - <<'PY'
from pathlib import Path
refs = sorted(p.name for p in Path('.agents/skills/project-extension-requesting-code-review/references').glob('*.md'))
print(refs)
assert len(refs) <= 2, refs
print('project review references merged')
PY`

Expected: 输出不超过 2 个引用页，随后打印 `project review references merged`

### Task 4: 把 Skill 编写方法论迁入 `project-extension-writing-skills`

**Files:**
- Modify: `.agents/skills/project-extension-writing-skills/SKILL.md`
- Move or Copy then Delete: `docs/harness-design-pattern.md`
- Modify or Create: `.agents/skills/project-extension-writing-skills/references/*.md`
- Delete or Merge: `.agents/skills/project-extension-writing-skills/references/harness-design-pattern.md`
- Delete or Merge: `.agents/skills/project-extension-writing-skills/references/structure-rules.md`
- Delete or Merge: `.agents/skills/project-extension-writing-skills/references/naming-rules.md`
- Delete or Merge: `.agents/skills/project-extension-writing-skills/references/migration-checklist.md`

- [ ] **Step 1: 把 `docs/harness-design-pattern.md` 迁入 Skill 私有体系**

目标：后续用户不再把它当作主 review 正文

- [ ] **Step 2: 合并 Skill 写作 references，减少多余入口**

建议最终分组：
- `writing-rules.md`
- `migration-checklist.md`

- [ ] **Step 3: 在主 Skill 中明确“这是 Agent 私有方法论，不是用户主 review 正文”**

Run: `python3 - <<'PY'
from pathlib import Path
assert not Path('docs/harness-design-pattern.md').exists(), 'docs/harness-design-pattern.md'
refs = sorted(p.name for p in Path('.agents/skills/project-extension-writing-skills/references').glob('*.md'))
print(refs)
assert len(refs) <= 2, refs
print('writing skill guidance moved')
PY`

Expected: 输出不超过 2 个引用页，随后打印 `writing skill guidance moved`

### Task 5: 收缩 `mpy-cli-tool` 与 `reference-sync` 的重复路由

**Files:**
- Modify: `.agents/skills/mpy-cli-tool/SKILL.md`
- Modify or Merge: `.agents/skills/mpy-cli-tool/references/*.md`
- Modify: `.agents/skills/reference-sync/SKILL.md`
- Modify or Merge: `.agents/skills/reference-sync/references/*.md`

- [ ] **Step 1: 把 `mpy-cli-tool` references 收缩到“命令与路径边界 / 排障”两类**

同时在规则盘点或并表清单中列出：
- `command-index.md` -> 新归属页
- `cli-reference.md` -> 新归属页
- `path-mapping.md` -> 新归属页
- `troubleshooting.md` -> 新归属页

- [ ] **Step 2: 把 `reference-sync` references 收缩到“同步规则 / 来源与质量”两类**

同时在规则盘点或并表清单中列出：
- `source-policy.md` -> 新归属页
- `sync-strategies.md` -> 新归属页
- `quality-checklist.md` -> 新归属页
- `traceability-rules.md` -> 新归属页

- [ ] **Step 3: 验证两个 Skill 的路由数量都已收缩**

Run: `python3 - <<'PY'
from pathlib import Path
checks = {
    '.agents/skills/mpy-cli-tool/references': 2,
    '.agents/skills/reference-sync/references': 2,
}
for folder, limit in checks.items():
    refs = sorted(p.name for p in Path(folder).glob('*.md'))
    print(folder, refs)
    assert len(refs) <= limit, (folder, refs)
print('tool skill references merged')
PY`

Expected: 每个目录输出不超过 2 个引用页，随后打印 `tool skill references merged`

### Task 6: 更新入口索引并完成最终结构验证

**Files:**
- Modify: `.agents/skills/AGENTS.md`
- Modify: `Readme.md`
- Verify: `docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md`
- Create or Modify: `docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-reference-merge-map.md`
- Verify: `.agents/skills/**`
- Verify: `docs/developer/**`

- [ ] **Step 1: 更新索引说明，确保只暴露修正后的主入口**

要点：
- `docs/developer/` 只再提 `strategy.md` 与 `tasks.md`
- 不再把 memory / TDD / harness 当作用户主 review 正文

- [ ] **Step 2: 验证活跃入口不再引用旧 Skill 名称或旧文件路径**

Run: `python3 - <<'PY'
from pathlib import Path
issues = []
for path in ['Readme.md', '.agents/skills/AGENTS.md', '.agents/skills/git-workflow/SKILL.md']:
    text = Path(path).read_text()
    for needle in [
        '.agents/skills/code-standards/SKILL.md',
        '.agents/skills/control-system/SKILL.md',
        '.agents/skills/embedded-development/SKILL.md',
        '.agents/skills/remote-spec-to-markdown/SKILL.md',
        '.agents/skills/mpy-cli/SKILL.md',
        'docs/developer/memory-review.md',
        'docs/developer/transportcar-memory-assets.md',
        'docs/developer/tdd-workflow.md',
    ]:
        if needle in text:
            issues.append((path, needle))
assert not issues, issues
print('entry docs updated for review-fix architecture')
PY`

Expected: `entry docs updated for review-fix architecture`

- [ ] **Step 3: 做最终结构验收**

Run: `python3 - <<'PY'
from pathlib import Path
assert {p.name for p in Path('docs/developer').glob('*.md')} == {'strategy.md', 'tasks.md'}
assert len(list(Path('.agents/skills/using-rules/references').glob('*.md'))) <= 3
assert len(list(Path('.agents/skills/project-extension-requesting-code-review/references').glob('*.md'))) <= 2
assert len(list(Path('.agents/skills/project-extension-writing-skills/references').glob('*.md'))) <= 2
assert len(list(Path('.agents/skills/mpy-cli-tool/references').glob('*.md'))) <= 2
assert len(list(Path('.agents/skills/reference-sync/references').glob('*.md'))) <= 2
inventory = Path('docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-rule-inventory.md').read_text()
for needle in ['code-standards', 'embedded-development', 'control-system', '| 原 Skill | 原规则原文 | 新归属 Skill / 正文 | 迁移状态 |']:
    assert needle in inventory, needle
assert '待迁移' not in inventory, '仍有规则未完成迁移'
assert '|  |' not in inventory, '规则盘点表存在空字段'
merge_map = Path('docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-reference-merge-map.md').read_text()
for needle in ['using-rules', 'project-extension-requesting-code-review', 'project-extension-writing-skills', 'mpy-cli-tool', 'reference-sync']:
    assert needle in merge_map, needle
assert '-> ' in merge_map, '引用页并表清单未明确写旧页到新页映射'
print('review-fix architecture verified')
PY`

Expected: `review-fix architecture verified`

- [ ] **Step 4: 验证所有对外入口都只把 `strategy.md` 与 `tasks.md` 视为用户 review 正文**

Run: `python3 - <<'PY'
from pathlib import Path
issues = []
for path in ['Readme.md', '.agents/skills/AGENTS.md', '.agents/skills/using-rules/SKILL.md', '.agents/skills/project-extension-requesting-code-review/SKILL.md']:
    text = Path(path).read_text()
    for needle in ['docs/developer/memory-review.md', 'docs/developer/transportcar-memory-assets.md', 'docs/developer/tdd-workflow.md', 'docs/harness-design-pattern.md']:
        if needle in text:
            issues.append((path, needle))
assert not issues, issues
print('user review surface verified')
PY`

Expected: `user review surface verified`

- [ ] **Step 5: 验证旧引用页都已写明并入去向，而不是只做数量收缩**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('docs/superpowers/plans/2026-03-23-skill-information-architecture-review-fixes-reference-merge-map.md').read_text()
for needle in [
    'code-style.md',
    'architecture-boundaries.md',
    'memory-budget.md',
    'embedded-workflow.md',
    'hardware-facts.md',
    'vision-semantics.md',
    'control-system.md',
    'protocol.md',
    'requirement-fit-checklist.md',
    'minimal-change-checklist.md',
    'competition-value-checklist.md',
    'style-consistency-checklist.md',
    'memory-impact-checklist.md',
    'harness-design-pattern.md',
    'structure-rules.md',
    'naming-rules.md',
    'migration-checklist.md',
    'command-index.md',
    'cli-reference.md',
    'path-mapping.md',
    'troubleshooting.md',
    'source-policy.md',
    'sync-strategies.md',
    'quality-checklist.md',
    'traceability-rules.md',
]:
    assert needle in text, needle
assert '->' in text
for needle in ['旧页', '新页']:
    assert needle in text, needle
print('reference merge map complete')
PY`

Expected: `reference merge map complete`
