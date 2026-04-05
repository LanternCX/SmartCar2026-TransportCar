# Boot Pin Mapping Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `boot` 启动脚本中的按钮引脚映射修正为真实硬件定义, 并把“未知硬件引脚必须先向用户确认, 禁止臆测”补充进嵌入式开发流程说明。

**Architecture:** 先通过单元测试锁定 `boot.py` 的按钮常量与启动路径使用的引脚名, 再以最小代码修改更新常量定义。随后仅修改 `embedded-development` skill 文档, 补充硬件引脚信息确认规则, 不扩大行为范围。

**Tech Stack:** Python, pytest, Markdown

---

### Task 1: 锁定 boot 按钮引脚映射

**Files:**
- Modify: `tests/unit/services/test_boot_script.py`
- Test: `tests/unit/services/test_boot_script.py`

**Step 1: Write the failing test**

在 `test_boot_script.py` 中增加断言, 锁定 `BUTTON1_PIN` 到 `BUTTON4_PIN` 分别为 `C8/C9/C14/C15`, 并让伪造引脚表使用 `C8/C9` 作为启动按钮输入。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_boot_script.py -q`
Expected: FAIL, 因为当前 `boot.py` 仍使用 `KEY1/KEY2`

### Task 2: 修正 boot 按钮常量

**Files:**
- Modify: `src/boot.py`
- Test: `tests/unit/services/test_boot_script.py`

**Step 1: Write minimal implementation**

把 `src/boot.py` 中按钮常量更新为:
- `BUTTON1_PIN = "C8"`
- `BUTTON2_PIN = "C9"`
- `BUTTON3_PIN = "C14"`
- `BUTTON4_PIN = "C15"`

保持现有启动逻辑只使用 Button 1/2, 不引入额外行为改动。

**Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_boot_script.py -q`
Expected: PASS

### Task 3: 补充嵌入式开发约束

**Files:**
- Modify: `.agents/skills/embedded-development/SKILL.md`

**Step 1: Update documentation**

在硬件相关约束中补充:
- 已知本项目 `boot.py` 的按钮 1-4 引脚分别为 `C8/C9/C14/C15`
- 以后遇到未知引脚, 接线, 板级资源映射时, 必须先向用户确认, 不得凭空假设

**Step 2: Verify wording**

检查新增文字只补充流程约束, 不改变其他设备开发规则。

### Task 4: 回归验证

**Files:**
- Test: `tests/unit/services/test_boot_script.py`

**Step 1: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_boot_script.py -q`
Expected: 全绿

**Step 2: Optional broader verification**

Run: `python3 -m pytest tests/unit/services/test_remote_control_script.py -q`
Expected: 相关启动链路仍为全绿
