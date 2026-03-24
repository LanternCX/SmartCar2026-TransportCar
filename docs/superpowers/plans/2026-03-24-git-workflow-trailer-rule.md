# git-workflow 提交尾注规则调整实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把“禁止默认追加 `Co-authored-by` 尾注”的新规则写入 `git-workflow` Skill。

**Architecture:** 只改 `.agents/skills/git-workflow/SKILL.md`，在提交规范附近增加单独的小节，明确默认禁止、例外条件和示例收口。保持最小改动，不扩散到其他 Skill。

**Tech Stack:** Markdown

---

### Task 1: 更新 git-workflow 提交尾注规则

**Files:**
- Modify: `.agents/skills/git-workflow/SKILL.md`

- [ ] **Step 1: 写出需要覆盖的新规则点**

要求至少包含：
- 默认不允许 agent 自动追加任何 `Co-authored-by`
- 只有用户明确要求且 co-author 是真人时才允许追加
- 删除旧的强制追加语义

- [ ] **Step 2: 最小改动更新 Skill 正文**

要求：
- 在提交规范附近新增单独的小节或等价位置
- 正文使用中文
- 示例保持为无 trailer 版本

- [ ] **Step 3: 自检规则是否清楚且不冲突**

Run: `python3 - <<'PY'
from pathlib import Path
text = Path('.agents/skills/git-workflow/SKILL.md').read_text()
for needle in [
    'Co-authored-by',
    '默认不追加',
    '用户明确要求',
    '真人',
]:
    assert needle in text, needle
print('git-workflow trailer rule updated')
PY`

Expected: `git-workflow trailer rule updated`
