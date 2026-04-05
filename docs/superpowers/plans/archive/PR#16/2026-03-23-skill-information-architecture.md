# Skill 信息架构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> 收口后补记: 本计划保留的是当时的实施语境。当前生效口径是“单一正文事实源, 但落点不再默认都在根 `docs/`”; 其中 `mpy-cli` 与 OpenArt 协议正文已分别迁入 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` 与 `.agents/skills/using-rules/references/openart-protocol.md`。

**Goal:** 重组仓库内 Skill 体系, 建立“单一正文 + Skill 路由 + references 引用页”的结构, 并落地首批本地扩展 Skill。

**Architecture:** 保留流程型与工具型 Skill 的独立性, 把知识型 Skill 收敛到 `using-rules` 路由入口, 文档正文统一保持单一事实源, 但正式落点按归属决定: 有些正文继续保留在 `docs/`, `mpy-cli` 与 OpenArt 协议正文则已迁入各自 Skill。Skill 侧通过 `references/` 提供查询入口。新增 `project-extension-writing-skills` 与 `project-extension-requesting-code-review` 作为对 superpowers 的本地补充 Skill, 同时精简 `mpy-cli-tool` 的主 Skill 结构。

**Tech Stack:** Markdown, repository-local skills under `.agents/skills`, filesystem markdown reference pages, pytest-free doc verification, grep-based reference checks

---

### Task 1: 前置条件检查与 spec 冻结确认

**Files:**
- Verify: `docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md`

- [ ] **Step 1: 确认 spec 已包含当前已同意的命名、覆盖规则和 review 总原则**

确认以下决策已存在于 spec 中:

- 扩展 superpowers 的本地 Skill 使用 `project-` 前缀
- 同名 Skill 不采用覆盖方案
- review 最高优先级固定为“满足要求 / 最小改动 / 对赛题有正贡献”

- [ ] **Step 2: 自检 spec 是否和当前讨论一致, 然后冻结为实现输入**

Run: `python3 - <<'PY'
from pathlib import Path
p = Path('docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md')
text = p.read_text()
for needle in ['project-extension-writing-skills', 'project-extension-requesting-code-review', '最小改动', '正贡献']:
    assert needle in text, needle
print('spec checks passed')
PY`

Expected: `spec checks passed`

### Task 2: 建立新的 Skill 目录骨架

**Files:**
- Create: `.agents/skills/using-rules/SKILL.md`
- Create: `.agents/skills/reference-sync/SKILL.md`
- Create: `.agents/skills/project-extension-writing-skills/SKILL.md`
- Create: `.agents/skills/project-extension-requesting-code-review/SKILL.md`
- Create: `.agents/skills/*/references/` (directories)

- [ ] **Step 1: 创建新 Skill 目录与空 references 目录**

Run: `mkdir -p .agents/skills/using-rules/references .agents/skills/reference-sync/references .agents/skills/project-extension-writing-skills/references .agents/skills/project-extension-requesting-code-review/references`

Expected: exit 0

- [ ] **Step 2: 为 4 个新 Skill 写最小可用主文档**

每个 `SKILL.md` 至少包含：

- frontmatter (`name`, `description`)
- Overview
- When to Use
- Routing Rules / Review Rules
- References entry points

- [ ] **Step 3: 检查新 Skill 是否都可被发现**

Run: `python3 - <<'PY'
from pathlib import Path
for name in ['using-rules','reference-sync','project-extension-writing-skills','project-extension-requesting-code-review']:
    p = Path('.agents/skills')/name/'SKILL.md'
    assert p.exists(), p
print('skill skeletons present')
PY`

Expected: `skill skeletons present`

### Task 3: 为 docs 正文建立 references 引用页入口

**Files:**
- Create: `.agents/skills/using-rules/references/*.md` (markdown reference pages)
- Create: `.agents/skills/project-extension-writing-skills/references/harness-design-pattern.md` (markdown reference page)
- Create: `.agents/skills/project-extension-requesting-code-review/references/*.md` (markdown reference pages)
- Create: `.agents/skills/mpy-cli-tool/references/*.md` (markdown reference pages)

- [ ] **Step 1: 选定并固定 `using-rules` 的首批唯一正文来源**

首批必须逐项映射为以下入口:

- `.agents/skills/using-rules/references/code-style.md` -> `docs/developer/tdd-workflow.md`
- `.agents/skills/using-rules/references/architecture-boundaries.md` -> `docs/developer/strategy.md`
- `.agents/skills/using-rules/references/memory-budget.md` -> `docs/developer/memory-review.md`
- `.agents/skills/using-rules/references/embedded-workflow.md` -> `docs/developer/tdd-workflow.md`
- `.agents/skills/using-rules/references/hardware-facts.md` -> `.agents/skills/using-rules/references/openart-protocol.md`
- `.agents/skills/using-rules/references/vision-semantics.md` -> `.agents/skills/using-rules/references/openart-protocol.md`
- `.agents/skills/using-rules/references/control-system.md` -> `docs/developer/strategy.md`
- `.agents/skills/using-rules/references/protocol.md` -> `.agents/skills/using-rules/references/openart-protocol.md`

- [ ] **Step 2: 在对应 Skill 下按文件逐项建立引用页**

Run: `为 using-rules/references/ 建立实现阶段规则引用页, 不包含 review 入口`

Expected: exit 0

- [ ] **Step 3: 验证引用页都指向存在文件**

Run: `python3 - <<'PY'
from pathlib import Path
for p in Path('.agents/skills').glob('*/references/*.md'):
    assert p.is_markdown reference page(), p
    assert p.resolve().exists(), p
print('reference markdown reference pages valid')
PY`

Expected: `reference markdown reference pages valid`

### Task 4: 精简 `mpy-cli-tool` 主 Skill 为路由入口

**Files:**
- Modify: `.agents/skills/mpy-cli-tool/SKILL.md`
- Create: `.agents/skills/mpy-cli-tool/references/command-index.md` (markdown reference page)
- Create: `.agents/skills/mpy-cli-tool/references/cli-reference.md` (markdown reference page)
- Create: `.agents/skills/mpy-cli-tool/references/path-mapping.md` (markdown reference page)
- Create: `.agents/skills/mpy-cli-tool/references/troubleshooting.md` (markdown reference page)

- [ ] **Step 1: 把 `mpy-cli-tool` 主 Skill 改成命令索引 + 路由结构**

保留：

- 什么时候用
- 简短命令索引概览
- 什么时候去看哪份参考
- 高风险边界提示

移除或下沉：

- 大段参数说明
- 完整长教程
- 冗长命令手册化内容

- [ ] **Step 2: 建立 `mpy-cli-tool` references 引用页**

建立以下映射:

- `command-index.md` -> `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- `cli-reference.md` -> `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- `path-mapping.md` -> `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- `troubleshooting.md` -> `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`

- [ ] **Step 3: 自检主 Skill 是否明显缩短且保留路由信息**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('.agents/skills/mpy-cli-tool/SKILL.md').read_text()
for needle in ['list', 'plan', 'deploy', 'references']:
    assert needle in text, needle
print('mpy-cli-tool routing skill ready')
PY`

Expected: `mpy-cli-tool routing skill ready`

### Task 5: 直接删除已废弃的旧知识型 Skill

**Files:**
- Modify: `.agents/skills/AGENTS.md`
- Modify: `Readme.md`
- Delete: `.agents/skills/code-standards/SKILL.md`
- Delete: `.agents/skills/code-standards/README.md`
- Delete: `.agents/skills/control-system/SKILL.md`
- Delete: `.agents/skills/embedded-development/SKILL.md`

- [ ] **Step 1: 删除 3 个旧知识型 Skill**

删除以下目录, 不保留兼容层或重定向文案：

- `.agents/skills/code-standards/`
- `.agents/skills/control-system/`
- `.agents/skills/embedded-development/`

- [ ] **Step 2: 更新仓库内 Skill 索引与入口说明**

把 `.agents/skills/AGENTS.md` 与 `Readme.md` 调整到新结构, 避免继续把 3 个旧 Skill 当主入口。

- [ ] **Step 3: 检查仓库入口文案不再把旧 Skill 当知识主入口**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('Readme.md').read_text()
assert 'project-extension-writing-skills' in text or 'using-rules' in text
print('entry docs updated')
PY`

Expected: `entry docs updated`

### Task 6: 删除 `remote-spec-to-markdown` 并把职责并入 `reference-sync`

**Files:**
- Modify: `.agents/skills/reference-sync/SKILL.md`
- Delete: `.agents/skills/remote-spec-to-markdown/SKILL.md`
- Modify: `.agents/skills/AGENTS.md`
- Modify: `Readme.md`

- [ ] **Step 1: 在 `reference-sync` 中吸收远端规则抓取与清洗职责**

把以下能力明确写入 `reference-sync/SKILL.md`:

- 远端网页抓取
- Markdown 清洗
- 来源追溯
- 仓库文档更新

- [ ] **Step 2: 删除 `remote-spec-to-markdown` Skill**

删除 `.agents/skills/remote-spec-to-markdown/` 目录, 不保留兼容层或重定向入口。

- [ ] **Step 3: 更新仓库入口索引**

确保索引不再把 `remote-spec-to-markdown` 当成独立主入口。

### Task 7: 补齐 `reference-sync` 与 `project-extension-writing-skills` 的引用与私有资产

**Files:**
- Modify: `.agents/skills/reference-sync/SKILL.md`
- Create: `.agents/skills/reference-sync/references/source-policy.md`
- Create: `.agents/skills/reference-sync/references/sync-strategies.md`
- Create: `.agents/skills/reference-sync/references/quality-checklist.md`
- Create: `.agents/skills/reference-sync/references/traceability-rules.md`
- Create: `.agents/skills/reference-sync/assets/import-template.md`
- Create: `.agents/skills/reference-sync/assets/source-record-template.md`
- Modify: `.agents/skills/project-extension-writing-skills/SKILL.md`
- Create: `.agents/skills/project-extension-writing-skills/references/structure-rules.md`
- Create: `.agents/skills/project-extension-writing-skills/references/naming-rules.md`
- Create: `.agents/skills/project-extension-writing-skills/references/migration-checklist.md`

- [ ] **Step 1: 为 `reference-sync` 建立 references 入口**

建立以下映射:

- `source-policy.md` -> `docs/problem_statement/sources.md`
- `sync-strategies.md` -> `docs/harness-design-pattern.md`
- `quality-checklist.md` -> `docs/problem_statement/README.md`
- `traceability-rules.md` -> `docs/problem_statement/sources.md`

- [ ] **Step 2: 为 `reference-sync` 创建 Skill 私有 assets**

创建 `import-template.md` 与 `source-record-template.md`, 并在文档中明确它们属于 Skill 私有模板资产, 不对应 `docs/` 正文。

- [ ] **Step 3: 为 `project-extension-writing-skills` 建立 references 入口**

建立以下映射:

- `harness-design-pattern.md` -> `docs/harness-design-pattern.md`
- `structure-rules.md` -> `docs/harness-design-pattern.md`
- `naming-rules.md` -> `docs/harness-design-pattern.md`
- `migration-checklist.md` -> `docs/harness-design-pattern.md`

### Task 8: 落地 `project-extension-requesting-code-review` 的本地审查入口

**Files:**
- Create: `.agents/skills/project-extension-requesting-code-review/SKILL.md`
- Create: `.agents/skills/project-extension-requesting-code-review/references/requirement-fit-checklist.md` (markdown reference page)
- Create: `.agents/skills/project-extension-requesting-code-review/references/minimal-change-checklist.md` (markdown reference page)
- Create: `.agents/skills/project-extension-requesting-code-review/references/competition-value-checklist.md` (markdown reference page)
- Create: `.agents/skills/project-extension-requesting-code-review/references/style-consistency-checklist.md` (markdown reference page)
- Create: `.agents/skills/project-extension-requesting-code-review/references/memory-impact-checklist.md` (markdown reference page)

- [ ] **Step 1: 在主 Skill 中固定 3 个最高优先级问题**

- 当前功能能否满足要求
- 当前实现是否满足最小改动
- 当前改动是否对完成赛题有正贡献

- [ ] **Step 2: 将 review references 全部接到唯一正文**

至少建立以下映射:

- `requirement-fit-checklist.md` -> `docs/developer/strategy.md`
- `minimal-change-checklist.md` -> `docs/developer/tasks.md`
- `competition-value-checklist.md` -> `docs/developer/strategy.md`
- `style-consistency-checklist.md` -> `docs/developer/tdd-workflow.md`
- `memory-impact-checklist.md` -> `docs/developer/memory-review.md`

- [ ] **Step 3: 自检 review Skill 是否覆盖仓库本地重点**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('.agents/skills/project-extension-requesting-code-review/SKILL.md').read_text()
for needle in ['满足要求', '最小改动', '正贡献', '内存']:
    assert needle in text, needle
print('project review skill ready')
PY`

Expected: `project review skill ready`

### Task 9: 最终结构验证

**Files:**
- Verify: `.agents/skills/**`
- Verify: `docs/**`

- [ ] **Step 1: 检查新 Skill 目录、主文档、references 入口都存在**

Run: `python3 - <<'PY'
from pathlib import Path
required = [
    '.agents/skills/using-rules/SKILL.md',
    '.agents/skills/reference-sync/SKILL.md',
    '.agents/skills/project-extension-writing-skills/SKILL.md',
    '.agents/skills/project-extension-requesting-code-review/SKILL.md',
]
for item in required:
    assert Path(item).exists(), item
print('core skill files present')
PY`

Expected: `core skill files present`

- [ ] **Step 2: 检查 references 引用页解析正常**

Run: `python3 - <<'PY'
from pathlib import Path
bad = []
for p in Path('.agents/skills').glob('*/references/*.md'):
    if not p.is_markdown reference page() or not p.resolve().exists():
        bad.append(str(p))
assert not bad, bad
print('all reference links resolve')
PY`

Expected: `all reference links resolve`

- [ ] **Step 3: 逐项检查“单一正文 + 引用页”策略是否成立**

Run: `python3 - <<'PY'
from pathlib import Path
approved = {
    Path('.agents/skills/using-rules/references/openart-protocol.md').resolve(),
    Path('.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md').resolve(),
    Path('docs/harness-design-pattern.md').resolve(),
    Path('docs/developer/memory-review.md').resolve(),
    Path('docs/developer/transportcar-memory-assets.md').resolve(),
    Path('docs/developer/strategy.md').resolve(),
    Path('docs/developer/tasks.md').resolve(),
    Path('docs/developer/tdd-workflow.md').resolve(),
    Path('docs/problem_statement/README.md').resolve(),
    Path('docs/problem_statement/sources.md').resolve(),
}
bad = []
for p in Path('.agents/skills').glob('*/references/*.md'):
    if not p.is_markdown reference page():
        bad.append(f'not_markdown reference page:{p}')
        continue
    target = p.resolve()
    if target not in approved:
        bad.append(f'bad_target:{p}->{target}')
assert not bad, bad
readme = Path('Readme.md').read_text()
assert 'using-rules' in readme
assert 'project-extension-writing-skills' in readme
for removed in [
    '.agents/skills/code-standards/SKILL.md',
    '.agents/skills/control-system/SKILL.md',
    '.agents/skills/embedded-development/SKILL.md',
    '.agents/skills/remote-spec-to-markdown/SKILL.md',
]:
    assert not Path(removed).exists(), removed
print('single-source strategy verified')
PY`

Expected: `single-source strategy verified`
