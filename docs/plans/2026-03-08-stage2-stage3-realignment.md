# Stage2/Stage3 Realignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把仓库中的设备化 TDD 流程纠偏为“stage2 自动化裸片 smoke + stage3 uart3 人工调试 + HIL 留证”。

**Architecture:** 复用现有 `diagnostic_mode` 与诊断快照接口，强化 `stage2` 探针的最小运行证明能力，同时把原先误标为 stage3 的自动脚本改回 stage2 runner。文档和测试同步更新，避免设备阶段定义继续漂移。

**Tech Stack:** Python, pytest, MicroPython, mpy-cli

---

### Task 1: 写入并验证 stage2 runner 的目标行为

**Files:**
- Modify: `tests/unit/tools/test_run_device_observe.py`

**Step 1: Write the failing test**

- 为 runner 增加对 `STAGE2 status=ok` 输出的成功解析测试
- 为 runner 增加对 `STAGE2 status=fail reason=...` 输出的失败归因测试
- 为 runner 增加“缺少关键 stage2 行时返回 `probe_failed`”测试

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/tools/test_run_device_observe.py -q`

**Step 3: Write minimal implementation**

- 把 runner 解析逻辑改为面向 stage2 smoke 输出

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/tools/test_run_device_observe.py -q`

### Task 2: 写入并验证 stage2 probe 强化行为

**Files:**
- Modify: `tests/unit/services/test_transport_car_diag_mode.py`
- Modify: `tools/stage2_smoke_probe.py`

**Step 1: Write the failing test**

- 为 `diagnostic_mode` 增加“关键快照构造不报错”测试
- 为 `diagnostic_mode` 增加“短时 step 不因硬件初始化缺失而抛异常”的最小测试

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -q`

**Step 3: Write minimal implementation**

- 在 `tools/stage2_smoke_probe.py` 中实例化 `TransportCar(diagnostic_mode=True)`
- 运行最小安全 smoke，并输出结构化 `STAGE2 ...` 行

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -q`

### Task 3: 同步文档与仓库约束

**Files:**
- Modify: `Readme.md`
- Modify: `tests/README.md`
- Modify: `tests/hil/README.md`
- Modify: `.agents/skills/git-workflow/SKILL.md`

**Step 1: Write the failing test**

- 无自动化测试；以文档一致性检查为准

**Step 2: Write minimal implementation**

- 明确 `stage2=自动化裸片 smoke`
- 明确 `stage3=uart3 人工调试流程`
- 明确 `HIL=真机留证`
- 在 `git-workflow` 中补充“不使用 superpowers 自带 worktree 工作流”

**Step 3: Run verification**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py tests/unit/tools/test_run_device_observe.py -q`
