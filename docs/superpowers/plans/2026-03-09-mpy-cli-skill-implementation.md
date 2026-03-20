# mpy-cli Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `.agents/skills/mpy-cli/SKILL.md` 补齐到与当前 `docs/mpy-cli.md` 的关键能力一致，尤其覆盖 `list`、端口发现策略与路径边界语义。

**Architecture:** 保持现有 skill 的章节骨架不变，采用最小改动补齐缺失能力。先用基线场景确认当前 skill 在串口未知场景下的遗漏，再更新 `SKILL.md` 的命令列表、核心语义、推荐流程、安全检查与故障入口，最后逐项对照文档验证覆盖面。

**Tech Stack:** Markdown, mpy-cli, repository skills documentation

---

### Task 1: 固化基线缺口

**Files:**
- Modify: none
- Test: `.agents/skills/mpy-cli/SKILL.md`
- Test: `docs/mpy-cli.md`

**Step 1: 记录当前 skill 的场景性缺口**

基于基线场景，确认当前 skill 在“串口未知时先发现设备再部署”场景下没有明确引导 `mpy-cli list`。

**Step 2: 提炼最小补齐目标**

把补齐范围限制为 `list`、扫描策略、路径语义、安全边界，不重写整个 skill。

### Task 2: 更新命令入口与推荐流程

**Files:**
- Modify: `.agents/skills/mpy-cli/SKILL.md`
- Test: `docs/mpy-cli.md`

**Step 1: 在 When to Use / Quick Commands 中补入 `list`**

新增 `mpy-cli list [--workers N] [--probe-timeout SECONDS] [--scan-mode MODE] [--reset]`，并在适用场景中加入“串口未知、需先发现设备”。

**Step 2: 调整 Recommended Workflow**

将流程改为“必要时 `init/config` -> 串口未知先 `list` -> `plan` -> `deploy` -> 单文件运维命令”，避免 agent 先要求用户手填端口。

### Task 3: 更新核心语义与安全边界

**Files:**
- Modify: `.agents/skills/mpy-cli/SKILL.md`
- Test: `docs/mpy-cli.md`

**Step 1: 补齐路径与目录语义**

补充 `.mpyignore` 相对 `source_dir`、`device_upload_dir` 作为远端前缀、`run/delete/tree` 的 `--path` 相对 `device_upload_dir` 等说明。

**Step 2: 补齐 `full` 模式边界**

明确 `full` 模式只清空上传目录，不清空整机根目录。

**Step 3: 补齐 `list` 扫描策略**

说明 `list` 默认优先探测成功缓存端口与当前可用端口交集，未发现设备再回退全量探测。

### Task 4: 更新安全检查与故障入口

**Files:**
- Modify: `.agents/skills/mpy-cli/SKILL.md`
- Test: `docs/mpy-cli.md`

**Step 1: 扩展 Safety Checklist**

增加“不确定端口时先 `list`”“无交互模式显式传 `--port`”“`full` 前确认目标端口与上传目录边界”。

**Step 2: 精简式补齐 Troubleshooting**

增加“扫描不确定时先回到 `list` / 调整扫描参数”的故障入口，保持内容短而可执行。

### Task 5: 对照文档验证

**Files:**
- Test: `.agents/skills/mpy-cli/SKILL.md`
- Test: `docs/mpy-cli.md`

**Step 1: 逐项核对关键覆盖点**

确认 skill 已覆盖以下事项：`list` 命令、扫描参数入口、`.mpyignore` 语义、`device_upload_dir` 语义、`run/delete/tree` 路径语义、`full` 清理范围、安全检查。

**Step 2: 检查风格一致性**

确认新增内容保持中文、延续现有章节结构、未扩展成完整命令参考。
