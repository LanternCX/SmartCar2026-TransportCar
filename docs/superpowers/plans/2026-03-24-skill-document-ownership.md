# Skill 文档归属调整实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `mpy-cli` 正式文档与 OpenArt 协议正文迁入对应 Skill，并让 `reference-sync` 独立维护来源记录与维护清单。

**Architecture:** 先把两份旧正文迁入各自 Skill 的 `references/`，再重写相关入口页与 Skill 路由，最后在 `reference-sync` 补齐来源登记和维护清单，并删除旧 `docs/` 路径与残留引用。整个过程不新增 Skill 私有 `docs/` 目录，只使用现有 `references/` 结构承接正式正文。

**Tech Stack:** Markdown, 仓库本地 Skill 文档, grep 内容检查, Python 路径校验脚本

> 收口后补记：本计划里原先的两个根 `docs/` 旧正文路径已删除，以下内容统一改写为描述性名称，仅用于保留迁移语境。

---

### Task 0: 盘点旧引用与现有维护对象

**Files:**
- Verify: `.agents/skills/reference-sync/SKILL.md`
- Verify: `.agents/skills/reference-sync/references/source-and-quality.md`
- Verify: `.agents/skills/reference-sync/references/sync-rules.md`
- Verify: `tests/unit/services/test_transport_car_logging.py`
- Verify: `.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`
- Verify: `.agents/skills/mpy-cli-tool/references/troubleshooting.md`
- Verify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Verify: `docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md`
- Verify: `docs/superpowers/specs/2026-03-23-skill-information-architecture-review-fixes-design.md`
- Verify: `docs/superpowers/specs/2026-03-14-physical-camera-id-overlap-design.md`
- Verify: `docs/superpowers/specs/2026-03-12-transport-runtime-decoupling-design.md`
- Verify: `docs/superpowers/specs/2026-03-13-dual-camera-single-state-machine-design.md`
- Verify: `docs/superpowers/specs/2026-03-09-mpy-cli-skill-design.md`
- Verify: `docs/superpowers/plans/2026-03-23-skill-information-architecture.md`
- Verify: `docs/superpowers/plans/2026-03-14-physical-camera-id-overlap.md`
- Verify: `docs/superpowers/plans/2026-03-13-dual-camera-single-state-machine.md`
- Verify: `docs/superpowers/plans/2026-03-10-global-log-system.md`
- Verify: `docs/superpowers/plans/2026-03-09-vision-bbox-observation.md`
- Verify: `docs/superpowers/plans/2026-03-09-mpy-cli-skill-implementation.md`
- Verify: `docs/superpowers/memory/milestone/entries/2026-03/2026-03-09-1.md`
- Create: `docs/superpowers/plans/2026-03-24-skill-document-ownership-reference-inventory.md`

- [ ] **Step 1: 先盘点仓库内所有根 `docs/` 下旧 OpenArt 协议正文与根 `docs/` 下旧 mpy-cli 正文的旧引用**

Run: `rg -n "docs/Protocol\.md|docs/mpy-cli\.md" . > /tmp/skill-doc-ownership-refs.txt`

Expected: 成功生成一份旧引用清单，供后续分类处理

- [ ] **Step 2: 把旧引用按处理策略整理成迁移清单**

Create: `docs/superpowers/plans/2026-03-24-skill-document-ownership-reference-inventory.md`

要求该清单至少包含 4 列：
- 路径
- 旧引用
- 处理策略
- 新落点

处理策略至少区分：
- 立即改写
- 保留历史记录但补迁移说明
- 需要同步更新测试

首批必须入清单的路径：
- `.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`
- `.agents/skills/mpy-cli-tool/references/troubleshooting.md`
- `.agents/skills/using-rules/references/hardware-and-protocol.md`
- `tests/unit/services/test_transport_car_logging.py`
- `docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md`
- `docs/superpowers/specs/2026-03-23-skill-information-architecture-review-fixes-design.md`
- `docs/superpowers/specs/2026-03-14-physical-camera-id-overlap-design.md`
- `docs/superpowers/specs/2026-03-12-transport-runtime-decoupling-design.md`
- `docs/superpowers/specs/2026-03-13-dual-camera-single-state-machine-design.md`
- `docs/superpowers/specs/2026-03-09-mpy-cli-skill-design.md`
- `docs/superpowers/plans/2026-03-23-skill-information-architecture.md`
- `docs/superpowers/plans/2026-03-14-physical-camera-id-overlap.md`
- `docs/superpowers/plans/2026-03-13-dual-camera-single-state-machine.md`
- `docs/superpowers/plans/2026-03-10-global-log-system.md`
- `docs/superpowers/plans/2026-03-09-vision-bbox-observation.md`
- `docs/superpowers/plans/2026-03-09-mpy-cli-skill-implementation.md`
- `docs/superpowers/memory/milestone/entries/2026-03/2026-03-09-1.md`

- [ ] **Step 3: 盘点 `reference-sync` 现有需要继续维护的文档对象**

Run: `python3 - <<'PY'
from pathlib import Path
for path in [
    '.agents/skills/reference-sync/SKILL.md',
    '.agents/skills/reference-sync/references/source-and-quality.md',
    '.agents/skills/reference-sync/references/sync-rules.md',
]:
    print(f'===== {path} =====')
    print(Path(path).read_text())
PY`

Expected: 能看出当前 `reference-sync` 已覆盖的问题文档集与相关维护边界

- [ ] **Step 4: 验证迁移清单至少覆盖测试、Skill 引用页和历史文档三类对象**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('docs/superpowers/plans/2026-03-24-skill-document-ownership-reference-inventory.md').read_text()
for needle in [
    'tests/unit/services/test_transport_car_logging.py',
    '.agents/skills/using-rules/references/hardware-and-protocol.md',
    'docs/superpowers/specs/',
]:
    assert needle in text, needle
print('reference inventory covers key categories')
PY`

Expected: `reference inventory covers key categories`

### Task 1: 迁移 `mpy-cli` 正式正文到 `mpy-cli-tool`

**Files:**
- Create: `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- Modify: `.agents/skills/mpy-cli-tool/SKILL.md`
- Modify: `.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`
- Modify: `.agents/skills/mpy-cli-tool/references/troubleshooting.md`
- Delete: 根 `docs/` 下旧 mpy-cli 正文

- [ ] **Step 1: 先把旧 `mpy-cli` 正文完整复制到新正式落点**

Create: `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`

要求：
- 以根 `docs/` 下旧 mpy-cli 正文为基础迁移完整正文
- 删除正文中的来源追溯类维护信息；保留面向使用者的完整命令说明、路径边界、无交互用法和排障内容
- 标题与章节命名允许按 Skill 语境轻微收敛，但不得丢失原有有效信息

- [ ] **Step 2: 运行正文完整性检查，确认关键章节已迁入**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md').read_text()
for needle in [
    '# mpy-cli',
    '## Quick Start',
    '## CLI 参数总览',
    'mpy-cli deploy',
    'device_upload_dir',
]:
    assert needle in text, needle
print('mpy-cli manual migrated')
PY`

Expected: `mpy-cli manual migrated`

- [ ] **Step 3: 重写 `mpy-cli-tool/SKILL.md`，让它明确路由到完整正文**

Modify: `.agents/skills/mpy-cli-tool/SKILL.md`

要求至少明确：
- 这是 `mpy-cli` 的统一入口
- 完整命令手册位于 `references/mpy-cli-manual.md`
- 命令索引与风险边界仍保留在主 Skill 中

- [ ] **Step 4: 重写两个轻量入口页，改为指向新正式正文**

Modify:
- `.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`
- `.agents/skills/mpy-cli-tool/references/troubleshooting.md`

要求：
- 明确正文唯一落点为 `references/mpy-cli-manual.md`
- 指向该正文中的对应主题，而不是继续指向根 `docs/` 下旧 mpy-cli 正文

- [ ] **Step 5: 删除旧根 `docs/` 下 mpy-cli 正文并确认仓库内没有残留引用**

Run: `python3 - <<'PY'
from pathlib import Path
legacy_doc_removed = not Path('.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md').exists()
assert legacy_doc_removed is False
print('legacy mpy-cli doc removed')
PY`

Expected: `legacy mpy-cli doc removed`

Run: `rg -n "docs/mpy-cli\.md|`docs/mpy-cli\.md`" .`

Expected: 不再出现任何指向旧根 `docs/` 下 mpy-cli 正文的引用

### Task 2: 迁移 OpenArt 协议正文到 `using-rules`

**Files:**
- Create: `.agents/skills/using-rules/references/openart-protocol.md`
- Modify: `.agents/skills/using-rules/SKILL.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Delete: 根 `docs/` 下旧 OpenArt 协议正文

- [ ] **Step 1: 把现有协议正文迁入 `using-rules` 新正式落点**

Create: `.agents/skills/using-rules/references/openart-protocol.md`

要求：
- 以根 `docs/` 下旧 OpenArt 协议正文为基础迁移完整协议内容
- 删除来源追溯类维护信息；保留协议目的、链路约定、字段语义、示例、兼容说明与迁移建议
- 文件名和标题明确体现这是 OpenArt 协议正式正文

- [ ] **Step 2: 运行协议完整性检查，确认关键部分没有丢失**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('.agents/skills/using-rules/references/openart-protocol.md').read_text()
for needle in [
    'OpenArt 与 RT1021 通信协议',
    '?frame=<camera_id>',
    'frame_end=1',
    '?vision',
    'UART6',
]:
    assert needle in text, needle
print('openart protocol migrated')
PY`

Expected: `openart protocol migrated`

- [ ] **Step 3: 更新 `using-rules` 主入口与协议总入口页**

Modify:
- `.agents/skills/using-rules/SKILL.md`
- `.agents/skills/using-rules/references/hardware-and-protocol.md`

要求：
- 主 Skill 继续把硬件与协议问题路由到 `hardware-and-protocol.md`
- `hardware-and-protocol.md` 明确把完整协议正文路由到 `references/openart-protocol.md`
- 现有已确认硬件事实段落继续保留，不把它们和长协议正文混成一页

- [ ] **Step 4: 更新依赖旧协议路径的测试或校验文件**

Modify: `tests/unit/services/test_transport_car_logging.py`

要求：
- 把直接读取旧根 `docs/` 下 OpenArt 协议正文的位置改到新正式正文路径
- 保持原测试意图不变，只更新事实源路径

- [ ] **Step 5: 删除旧根 `docs/` 下 OpenArt 协议正文并确认仓库内没有残留引用**

Run: `python3 - <<'PY'
from pathlib import Path
legacy_doc_removed = not Path('.agents/skills/using-rules/references/openart-protocol.md').exists()
assert legacy_doc_removed is False
print('legacy protocol doc removed')
PY`

Expected: `legacy protocol doc removed`

Run: `rg -n "docs/Protocol\.md|`docs/Protocol\.md`" .`

Expected: 不再出现任何指向旧根 `docs/` 下 OpenArt 协议正文的引用

### Task 3: 为 `reference-sync` 补齐来源登记与维护清单

**Files:**
- Modify: `.agents/skills/reference-sync/SKILL.md`
- Create: `.agents/skills/reference-sync/references/source-registry.md`
- Create: `.agents/skills/reference-sync/references/maintenance-checklist.md`
- Modify: `.agents/skills/reference-sync/references/source-and-quality.md`
- Modify: `.agents/skills/reference-sync/references/sync-rules.md`

- [ ] **Step 1: 创建来源登记页，至少覆盖 `mpy-cli` 与 OpenArt 协议**

前置要求：先对照 `docs/superpowers/plans/2026-03-24-skill-document-ownership-reference-inventory.md` 与现有 `reference-sync` 内容，列出除 `mpy-cli`、OpenArt 协议之外仍需继续维护的文档对象。

Create: `.agents/skills/reference-sync/references/source-registry.md`

要求每条记录至少包含：
- 文档名称
- 外部或历史来源
- 当前正式落点
- 更新时机或同步触发条件

- [ ] **Step 2: 创建维护清单页，列出所有需要持续维护的文档**

Create: `.agents/skills/reference-sync/references/maintenance-checklist.md`

要求：
- 至少包含 `mpy-cli` 正式文档与 OpenArt 协议正文
- 必须把当前 `reference-sync` 原本负责的问题文档集等既有维护对象继续纳入，不得因为本次迁移而丢失旧条目
- 每个条目至少包含：来源、正式落点、维护检查项
- 使用稳定 checklist 格式，便于后续继续追加条目

- [ ] **Step 3: 重写 `reference-sync` 主入口与两个引用页，让它们路由到新维护文档**

Modify:
- `.agents/skills/reference-sync/SKILL.md`
- `.agents/skills/reference-sync/references/source-and-quality.md`
- `.agents/skills/reference-sync/references/sync-rules.md`

要求：
- 主 Skill 说明正式正文不在这里维护
- `source-and-quality.md` 路由到 `source-registry.md` 与 `maintenance-checklist.md`
- `sync-rules.md` 说明更新正文时必须同时检查来源登记与维护清单

- [ ] **Step 4: 验证来源登记与维护清单相互一致**

Run: `python3 - <<'PY'
from pathlib import Path
registry = Path('.agents/skills/reference-sync/references/source-registry.md').read_text()
checklist = Path('.agents/skills/reference-sync/references/maintenance-checklist.md').read_text()
for needle in ['mpy-cli', 'OpenArt', 'problem_statement']:
    assert needle in registry, needle
    assert needle in checklist, needle
print('reference sync registry and checklist aligned')
PY`

Expected: `reference sync registry and checklist aligned`

### Task 4: 收口旧引用并完成最终验证

**Files:**
- Modify: `docs/superpowers/plans/2026-03-24-skill-document-ownership-reference-inventory.md`
- Verify: `.agents/skills/mpy-cli-tool/SKILL.md`
- Verify: `.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md`
- Verify: `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md`
- Verify: `.agents/skills/using-rules/SKILL.md`
- Verify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Verify: `.agents/skills/using-rules/references/openart-protocol.md`
- Verify: `.agents/skills/reference-sync/SKILL.md`
- Verify: `.agents/skills/reference-sync/references/source-registry.md`
- Verify: `.agents/skills/reference-sync/references/maintenance-checklist.md`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Modify: `docs/superpowers/specs/2026-03-23-skill-information-architecture-design.md`
- Modify: `docs/superpowers/specs/2026-03-23-skill-information-architecture-review-fixes-design.md`
- Modify: `docs/superpowers/specs/2026-03-14-physical-camera-id-overlap-design.md`
- Modify: `docs/superpowers/specs/2026-03-12-transport-runtime-decoupling-design.md`
- Modify: `docs/superpowers/specs/2026-03-13-dual-camera-single-state-machine-design.md`
- Modify: `docs/superpowers/specs/2026-03-09-mpy-cli-skill-design.md`
- Modify: `docs/superpowers/plans/2026-03-23-skill-information-architecture.md`
- Modify: `docs/superpowers/plans/2026-03-14-physical-camera-id-overlap.md`
- Modify: `docs/superpowers/plans/2026-03-13-dual-camera-single-state-machine.md`
- Modify: `docs/superpowers/plans/2026-03-10-global-log-system.md`
- Modify: `docs/superpowers/plans/2026-03-09-vision-bbox-observation.md`
- Modify: `docs/superpowers/plans/2026-03-09-mpy-cli-skill-implementation.md`
- Modify: `docs/superpowers/memory/milestone/entries/2026-03/2026-03-09-1.md`

- [ ] **Step 1: 依据迁移清单逐类处理旧引用**

要求：
- 对需要立即改写的文件，直接替换到新 Skill 路径
- 对保留历史记录的文档，补充迁移说明，避免留下断链
- 对测试文件，改到新事实源路径后保持断言语义不变
- 上述 `Files` 中列出的具体文件必须逐个处理，不允许只改通配范围说明

- [ ] **Step 2: 检查三个 Skill 的完整路由链都能到达目标正文或维护页**

Run: `python3 - <<'PY'
from pathlib import Path
checks = {
    '.agents/skills/mpy-cli-tool/SKILL.md': 'references/command-and-path-boundaries.md',
    '.agents/skills/mpy-cli-tool/references/command-and-path-boundaries.md': 'references/mpy-cli-manual.md',
    '.agents/skills/using-rules/SKILL.md': 'references/hardware-and-protocol.md',
    '.agents/skills/using-rules/references/hardware-and-protocol.md': 'references/openart-protocol.md',
    '.agents/skills/reference-sync/SKILL.md': 'references/maintenance-checklist.md',
}
for path, needle in checks.items():
    text = Path(path).read_text()
    assert needle in text, (path, needle)
print('skill routing verified')
PY`

Expected: `skill routing verified`

- [ ] **Step 3: 检查正式正文不含来源追溯类维护文字**

Run: `python3 - <<'PY'
from pathlib import Path
for path in [
    '.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md',
    '.agents/skills/using-rules/references/openart-protocol.md',
]:
    text = Path(path).read_text()
    banned = ['来源：', '原始链接', '同步来源', '抓取自']
    assert not any(word in text for word in banned), path
print('formal docs cleaned')
PY`

Expected: `formal docs cleaned`

- [ ] **Step 4: 运行全局残留引用检查**

Run: `rg -n "docs/Protocol\.md|docs/mpy-cli\.md" .`

Expected: 无输出

- [ ] **Step 5: 运行最终文件存在性检查**

Run: `python3 - <<'PY'
from pathlib import Path
required = [
    '.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md',
    '.agents/skills/using-rules/references/openart-protocol.md',
    '.agents/skills/reference-sync/references/source-registry.md',
    '.agents/skills/reference-sync/references/maintenance-checklist.md',
]
missing = [p for p in required if not Path(p).exists()]
assert not missing, missing
print('skill document ownership migration complete')
PY`

Expected: `skill document ownership migration complete`

- [ ] **Step 6: Commit**

```bash
git add .agents/skills/mpy-cli-tool .agents/skills/using-rules .agents/skills/reference-sync docs/superpowers/specs/2026-03-24-skill-document-ownership-design.md docs/superpowers/plans/2026-03-24-skill-document-ownership.md
git commit -m "refactor(agent): relocate skill-owned docs and sync registry"
```

提交前补充暂存范围：
- `docs/superpowers/plans/2026-03-24-skill-document-ownership-reference-inventory.md`
- `tests/unit/services/test_transport_car_logging.py`
- 本计划中明确列出的历史 `spec` / `plan` / `memory` 文档修订文件

说明：仅在用户确认提交信息后执行提交；若用户未要求提交，则停在验证完成状态。
