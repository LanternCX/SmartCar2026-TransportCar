# 开发者文档拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重写原有设计正文的前提下，把根 `README.md` 做薄，并把开发者需要保留的总体方案、电控设计、视觉设计内容拆分到 `docs/developer/`。

**Architecture:** 先用文档断言式检查锁定 README 必须删去和必须保留的内容，再按原文段落迁移到 `strategy.md`、新增的 `control.md`、新增的 `vision.md`。整个过程只允许拆分、去重、归位和最小必要衔接，不做系统重写，并在每个任务后用内容检查命令验证结果。

**Tech Stack:** Markdown, `python3 -m pytest`, `rg`

---

## 目标文件结构

- 修改：`README.md`
- 修改：`docs/developer/strategy.md`
- 创建：`docs/developer/control.md`
- 创建：`docs/developer/vision.md`
- 参考：`docs/developer/tasks.md`
- 参考：`docs/superpowers/specs/2026-03-24-developer-doc-split-design.md`

## README 迁移对照表

| README 现有内容 | 动作 | 目标位置 | 处理规则 |
| --- | --- | --- | --- |
| `项目概述` | 保留并压缩 | `README.md` | 只保留入口级说明, 不重写核心项目描述 |
| `主要特性` | 拆分迁移 | `docs/developer/control.md` / `docs/developer/vision.md` / `docs/developer/strategy.md` | 只搬运其中的上层设计判断, 不保留功能罗列表达 |
| `开发工作流` | 删除 | 无 | 不属于本次开发者主文档主线 |
| `开发规范与技能指南` | 删除 | 无 | Agent / Skill / AI 入口不保留在 README 主体 |
| `通信配置` | 删除或仅保留极短导航 | 无 | 属于协议与链路细节, 不保留在主文档正文 |
| `车号与角色配置` | 拆分迁移 | `docs/developer/strategy.md` | 只保留主辅分工与角色边界判断 |
| `上电入口配置` | 拆分迁移 | `docs/developer/control.md` | 只保留启动入口的上层设计关系 |
| `前置要求` | 拆分迁移 | `docs/developer/control.md` | 保留辨识与校准在系统中的作用, 删除操作步骤 |
| `关键参数配置` | 删除 | 无 | 参数表不进入开发者主文档正文 |
| `代码架构说明` | 拆分迁移 | `docs/developer/control.md` | 只保留理解电控层次需要的结构说明 |
| `核心控制流程` | 迁移 | `docs/developer/control.md` | 原文搬运为主 |
| `控制模式详解` | 迁移 | `docs/developer/control.md` | 原文搬运为主 |
| `遥控协议` | 删除 | 无 | 协议正文不留在本次主文档 |
| `视觉状态机迁移` | 迁移 | `docs/developer/vision.md` | 原文搬运为主 |
| `控制算法` | 迁移 | `docs/developer/control.md` | 原文搬运为主 |
| `参数辨识` | 迁移 | `docs/developer/control.md` | 原文搬运为主 |
| `TODO List` | 删除 | 无 | 任务路线由 `docs/developer/tasks.md` 承接 |
| `快速开始指南` | 删除 | 无 | 操作手册类内容不保留 |
| `Q&A` | 迁移 | `docs/developer/control.md` | 必须完整保留核心问答判断 |
| `文件上传清单` | 删除 | 无 | 操作手册类内容不保留 |
| `贡献与维护指南` | 删除 | 无 | 不属于本次保留重点 |

## 细化迁移动作表

| README 现有内容 | 允许动作 | 禁止动作 |
| --- | --- | --- |
| `项目概述` | 保留原句主干, 仅删实现细节堆叠 | 改写成全新摘要 |
| `主要特性` | 拆成若干原句迁入目标文档 | 自行重写成功能卖点文案 |
| `前置要求` | 仅保留“为什么需要辨识/校准”的原句或原句主干 | 保留步骤说明或改写成新操作指南 |
| `代码架构说明` | 仅提取理解分层所需的原句或短段落 | 逐文件重写、重新发明结构说明 |
| `Q&A` | 原样迁移问答正文 | 改写问答判断或压缩成摘要 |

## 混合段落处理规则

- 同一段若同时含“设计判断 + 实现细节”，优先保留设计判断到对应专题文档，删除细节部分，最多补一句导航。
- 若段落主体是操作步骤、参数表、字段表、上传说明，即使夹带少量背景，也按删除处理，不单独保留。
- 若段落主体是设计取舍，但带少量示例或说明，可原样迁移后只删去明显实现细节，不重写主判断。
- 现成例子：
  - `前置要求` 中保留“参数辨识/陀螺仪校准为什么存在”，删除“长按哪个按钮进入”这类步骤细节。
  - `车号与角色配置` 中保留“主车/辅车能力边界”，删除拨码组合表。
  - `控制模式详解` 中保留模式设计意图，删除协议命令示例。

## 关键章节执行清单

- `README.md`
  - 保留：`项目概述`
  - 新增或整理：`仓库定位`、`开发者文档`
  - 删除整章：`开发工作流`、`开发规范与技能指南`、`开发和配置指南`、`代码架构说明`、`遥控协议`、`TODO List`、`快速开始指南`、`Q&A`、`文件上传清单`、`贡献与维护指南`
- `docs/developer/control.md`
  - 从 README 原样迁移并整理为章节：`上电入口配置`、`核心控制流程`、`控制模式详解`、`控制算法`、`参数辨识`、`Q&A`
  - 从 `前置要求`、`代码架构说明` 提取上层设计判断并并入相应章节
- `docs/developer/vision.md`
  - 从 README 原样迁移并整理为章节：`视觉状态机迁移`
  - 从 `项目概述`、`主要特性` 中抽出与视觉职责、双摄、主车协同直接相关的原文判断
- `docs/developer/strategy.md`
  - 保留现有主体结构和原文
  - 只做最小去重，不新增控制算法、协议、视觉状态机迁移等专题展开

## 必保留原句锚点

以下锚点统一以“去掉 Markdown 反引号后的纯文本写法”为准；测试和迁移都使用这一套写法，避免格式差异误判。

- `README.md -> docs/developer/strategy.md`
  - `主车负责环境理解、任务决策与唯一任务状态机维护。`
  - `辅车负责配合执行与状态回传, 不处理图像数据。`
- `README.md -> docs/developer/control.md`
  - `当前 boot.py 已将“角色选择”和“启动入口”拆开：`
  - `目标速度 → 前馈补偿 + 速度环 PID 输出 → PWM 占空比 → 电机`
  - `由于全向轮的性质，实际上车模在运动过程中各轮的阻尼存在各向异性`
- `README.md -> docs/developer/vision.md`
  - `当前仓库已经接管原 OpenArt 端的状态机跳转逻辑。`
  - `OpenArt：只负责视觉识别，并通过 UART6 连续回传完整识别框 left,top,right,bottom。`
  - `RT1021 主控：负责状态机跳转、里程计判定、推行/返回阶段切换，以及 dx/dy/d_angle 风格控制意图的生成。`
- `README.md -> docs/developer/control.md (Q&A)`
  - `因为闭环位置依赖的是轮速积分 + 运动学解算。`
  - `最后的效果就是光是放着不动距离都在涨。`
  - `因此通过加锁，我们可以避免两个异步线程通信的时候出现的各种问题`

## 任务分解原则

- 所有正文优先直接搬运原文段落，不先改写再落位。
- 只允许最小必要编辑：标题、顺序、少量衔接、明显重复删除。
- 每个任务都先写“文档断言测试”，先看到失败，再做正文调整。
- 文档断言测试优先用 `pytest` 调用轻量文本检查，避免人工目测代替验证。
- 禁止因为文风统一或摘要优化，对迁移后的正文做大段改写。

### Task 1: 建立文档断言测试基线

**Files:**
- Create: `tests/unit/test_developer_docs_split.py`
- Reference: `README.md`
- Reference: `docs/developer/strategy.md`
- Reference: `docs/superpowers/specs/2026-03-24-developer-doc-split-design.md`

- [ ] **Step 1: 写失败测试，锁定本次拆分的外部结果**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_keeps_only_entry_level_sections() -> None:
    readme = read_text("README.md")
    assert "## 项目概述" in readme
    assert "## 仓库定位" in readme
    assert "## 开发者文档" in readme
    assert "docs/developer/control.md" in readme
    assert "docs/developer/vision.md" in readme
    assert "## 开发和配置指南" not in readme
    assert "## 遥控协议" not in readme
    assert "## 快速开始指南" not in readme
    assert "## Q&A" not in readme


def test_strategy_stays_high_level() -> None:
    strategy = read_text("docs/developer/strategy.md")
    assert "# 项目核心方案" in strategy
    assert "## 2. 方案路径" in strategy
    assert "## 4. 搬运策略" in strategy
    assert "主车负责环境理解、任务决策与唯一任务状态机维护。" in strategy
    assert "辅车负责配合执行与状态回传, 不处理图像数据。" in strategy
    assert "视觉状态机迁移" not in strategy
    assert "## 控制算法" not in strategy


def test_new_developer_docs_exist() -> None:
    assert (ROOT / "docs/developer/control.md").exists()
    assert (ROOT / "docs/developer/vision.md").exists()


def test_readme_removes_agent_and_protocol_sections() -> None:
    readme = read_text("README.md")
    assert "### 开发规范与技能指南" not in readme
    assert "**核心技能**" not in readme
    assert "### 通信配置" not in readme
    assert "## 遥控协议" not in readme
```

- [ ] **Step 2: 运行测试，确认它先失败**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: FAIL，失败原因至少包含 `docs/developer/control.md` 或 `docs/developer/vision.md` 不存在，且 README 仍保留旧厚内容。

- [ ] **Step 3: 只补最小测试辅助代码，不改正文**

```python
# 本任务不需要额外生产代码；仅保留最小测试文件本身
```

- [ ] **Step 4: 再次运行测试，确认仍是正文缺失导致失败**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: FAIL，且失败集中在文档尚未拆分完成，而不是测试文件本身报错。

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_developer_docs_split.py
git commit -m "test(docs): add developer doc split assertions"
```

### Task 2: 瘦身 README 并建立开发者入口

**Files:**
- Modify: `README.md`
- Test: `tests/unit/test_developer_docs_split.py`
- Reference: `docs/superpowers/specs/2026-03-24-developer-doc-split-design.md`

- [ ] **Step 1: 先补失败测试，明确 README 入口形态**

```python
def test_readme_links_all_core_developer_docs() -> None:
    readme = read_text("README.md")
    assert "docs/developer/strategy.md" in readme
    assert "docs/developer/control.md" in readme
    assert "docs/developer/vision.md" in readme
    assert "docs/developer/tasks.md" in readme


def test_readme_removes_required_split_sections() -> None:
    readme = read_text("README.md")
    assert "### 上电入口配置" not in readme
    assert "### 核心控制流程" not in readme
    assert "## 控制算法" not in readme
    assert "## 视觉状态机迁移" not in readme
```

- [ ] **Step 2: 运行测试，确认 README 相关断言失败**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: FAIL，失败原因指向 README 仍包含旧厚内容或缺少新入口链接。

- [ ] **Step 3: 用最小改动精简 `README.md`**

```markdown
# 2025 智能车蚂蚁搬家组 - 搬运车模代码

## 项目概述

<保留现有简介的原句主干, 仅删去实现细节堆叠, 不重写项目判断>

## 仓库定位

<用最少新增文字说明这是搬运车模控制与开发仓库>

## 开发者文档

- [总体方案](docs/developer/strategy.md)
- [电控设计](docs/developer/control.md)
- [视觉设计](docs/developer/vision.md)
- [任务路线](docs/developer/tasks.md)
```

- [ ] **Step 4: 运行测试，确认 README 断言通过**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: 与 README 相关的断言 PASS，剩余失败集中在专题文档尚未创建或专题内容尚未迁移。

- [ ] **Step 5: Commit**

```bash
git add README.md tests/unit/test_developer_docs_split.py
git commit -m "docs(readme): slim project entry for developers"
```

### Task 3: 拆出电控设计文档并保留 Q&A

**Files:**
- Create: `docs/developer/control.md`
- Modify: `README.md`
- Test: `tests/unit/test_developer_docs_split.py`

- [ ] **Step 1: 先补失败测试，锁定电控文档边界和 Q&A 保留**

```python
def test_electrical_control_doc_keeps_control_design_sections() -> None:
    electrical = read_text("docs/developer/control.md")
    assert "# 电控设计" in electrical
    assert "## 上电入口配置" in electrical
    assert "## 核心控制流程" in electrical
    assert "## 控制模式详解" in electrical
    assert "## 控制算法" in electrical
    assert "## 参数辨识" in electrical
    assert "## 设计决策 Q&A" in electrical


def test_electrical_control_doc_keeps_original_qa_decisions() -> None:
    electrical = read_text("docs/developer/control.md")
    assert "为什么不闭环位置只闭环航向角" in electrical
    assert "因为闭环位置依赖的是轮速积分 + 运动学解算" in electrical
    assert "为什么不使用 IMU 闭环位置" in electrical
    assert "最后的效果就是光是放着不动距离都在涨" in electrical
    assert "为什么要加锁" in electrical
    assert "因此通过加锁，我们可以避免两个异步线程通信的时候出现的各种问题" in electrical


def test_readme_moves_qa_out_to_electrical_control_doc() -> None:
    readme = read_text("README.md")
    electrical = read_text("docs/developer/control.md")
    assert "## Q&A" not in readme
    assert "## 设计决策 Q&A" in electrical


def test_electrical_control_doc_keeps_required_original_sentences() -> None:
    electrical = read_text("docs/developer/control.md")
    assert "当前 boot.py 已将“角色选择”和“启动入口”拆开：" in electrical
    assert "目标速度 → 前馈补偿 + 速度环 PID 输出 → PWM 占空比 → 电机" in electrical
    assert "由于全向轮的性质，实际上车模在运动过程中各轮的阻尼存在各向异性" in electrical


def test_electrical_control_doc_gets_required_sections_from_readme() -> None:
    electrical = read_text("docs/developer/control.md")
    assert "## 上电入口配置" in electrical
    assert "## 核心控制流程" in electrical
    assert "## 控制算法" in electrical
    assert "## 参数辨识" in electrical
```

- [ ] **Step 2: 运行测试，确认电控文档断言失败**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: FAIL，失败原因指向 `docs/developer/control.md` 不存在或缺章节。

- [ ] **Step 3: 按原文拆出 `docs/developer/control.md`**

```markdown
# 电控设计

<从 README 原文直接迁移与电控相关的上层设计段落, 不重写正文；保留“当前 boot.py 已将‘角色选择’和‘启动入口’拆开：”等原句锚点>

## 核心控制流程
<迁移原 README 对应内容>

## 控制模式详解
<迁移原 README 对应内容>

## 控制算法
<迁移原 README 对应内容>

## 参数辨识
<迁移原 README 对应内容>

## 设计决策 Q&A
<迁移原 README 原问答正文，保留关键原句，不改写核心判断>
```

- [ ] **Step 4: 运行测试，确认电控文档断言通过**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: 电控文档相关断言 PASS，剩余失败集中在视觉文档或 strategy 收口。

- [ ] **Step 5: Commit**

```bash
git add README.md docs/developer/control.md tests/unit/test_developer_docs_split.py
git commit -m "docs(developer): split electrical control design"
```

### Task 4: 拆出视觉设计文档并收口 strategy

**Files:**
- Create: `docs/developer/vision.md`
- Modify: `docs/developer/strategy.md`
- Modify: `README.md`
- Test: `tests/unit/test_developer_docs_split.py`

- [ ] **Step 1: 先补失败测试，锁定视觉文档和 strategy 的上层边界**

```python
def test_vision_doc_keeps_visual_design_context() -> None:
    vision = read_text("docs/developer/vision.md")
    assert "# 视觉设计" in vision
    assert "## 视觉状态机迁移" in vision
    assert "OpenArt：只负责视觉识别" in vision
    assert "RT1021 主控：负责状态机跳转" in vision
    assert "### 键值对格式说明" not in vision
    assert "### 信息查询（Query Interface）" not in vision


def test_strategy_keeps_only_high_level_direction() -> None:
    strategy = read_text("docs/developer/strategy.md")
    assert "## 2. 方案路径" in strategy
    assert "## 4. 搬运策略" in strategy
    assert "视觉状态机迁移" not in strategy
    assert "控制算法" not in strategy


def test_visual_state_machine_section_moves_to_vision_doc() -> None:
    strategy = read_text("docs/developer/strategy.md")
    vision = read_text("docs/developer/vision.md")
    assert "视觉状态机迁移" not in strategy
    assert "视觉状态机迁移" in vision
    assert "迁移后的内部状态机仍保持以下阶段" in vision


def test_vision_doc_keeps_required_original_sentences() -> None:
    vision = read_text("docs/developer/vision.md")
    assert "当前仓库已经接管原 OpenArt 端的状态机跳转逻辑。" in vision
    assert "OpenArt：只负责视觉识别，并通过 UART6 连续回传完整识别框 left,top,right,bottom。" in vision
    assert "RT1021 主控：负责状态机跳转、里程计判定、推行/返回阶段切换，以及 dx/dy/d_angle 风格控制意图的生成。" in vision


def test_strategy_keeps_role_boundary_original_sentences() -> None:
    strategy = read_text("docs/developer/strategy.md")
    assert "主车负责环境理解、任务决策与唯一任务状态机维护。" in strategy
    assert "辅车负责配合执行与状态回传, 不处理图像数据。" in strategy
```

- [ ] **Step 2: 运行测试，确认视觉 / strategy 断言失败**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: FAIL，失败原因指向 `docs/developer/vision.md` 尚不存在或 `strategy.md` 仍含不该保留内容。

- [ ] **Step 3: 按原文拆出 `docs/developer/vision.md` 并微调 `strategy.md`**

```markdown
# 视觉设计

<迁移 README 中与视觉职责、双摄、视觉状态机迁移、主车协同相关的原文段落, 不重写正文；保留 OpenArt / RT1021 职责原句>
```

```markdown
# 项目核心方案

<保留现有 strategy 原文主体，只做最小必要收口，不新增技术展开>
```

- [ ] **Step 4: 运行测试，确认主断言全部通过**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/developer/strategy.md docs/developer/vision.md tests/unit/test_developer_docs_split.py
git commit -m "docs(developer): split vision design and refine strategy"
```

### Task 5: 去重收尾与整体校验

**Files:**
- Modify: `README.md`
- Modify: `docs/developer/control.md`
- Modify: `docs/developer/vision.md`
- Modify: `docs/developer/strategy.md`
- Test: `tests/unit/test_developer_docs_split.py`

- [ ] **Step 1: 先补失败测试，锁定去重后的最终状态**

```python
def test_readme_no_longer_contains_split_out_sections() -> None:
    readme = read_text("README.md")
    assert "## 控制模式详解" not in readme
    assert "## 控制算法" not in readme
    assert "## Q&A" not in readme
    assert "## 视觉状态机迁移" not in readme


def test_developer_docs_form_complete_entry_set() -> None:
    readme = read_text("README.md")
    electrical = read_text("docs/developer/control.md")
    vision = read_text("docs/developer/vision.md")
    assert "docs/developer/control.md" in readme
    assert "docs/developer/vision.md" in readme
    assert "## 设计决策 Q&A" in electrical
    assert "# 视觉设计" in vision


def test_split_sections_have_unique_home() -> None:
    readme = read_text("README.md")
    strategy = read_text("docs/developer/strategy.md")
    electrical = read_text("docs/developer/control.md")
    vision = read_text("docs/developer/vision.md")
    assert "## 核心控制流程" not in readme
    assert "## 核心控制流程" in electrical
    assert "## 视觉状态机迁移" not in readme
    assert "## 视觉状态机迁移" in vision
    assert "主车负责环境理解、任务决策与唯一任务状态机维护。" in strategy
    assert "主车负责环境理解、任务决策与唯一任务状态机维护。" not in electrical
    assert "主车负责环境理解、任务决策与唯一任务状态机维护。" not in vision
    assert "因为闭环位置依赖的是轮速积分 + 运动学解算" in electrical
    assert "因为闭环位置依赖的是轮速积分 + 运动学解算" not in readme
    assert "因为闭环位置依赖的是轮速积分 + 运动学解算" not in vision
    assert "当前仓库已经接管原 OpenArt 端的状态机跳转逻辑。" in vision
    assert "当前仓库已经接管原 OpenArt 端的状态机跳转逻辑。" not in readme
    assert "当前仓库已经接管原 OpenArt 端的状态机跳转逻辑。" not in electrical
```

- [ ] **Step 2: 运行测试，确认最终去重断言先失败**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: 若仍有重复内容，应 FAIL 并指向残留章节。

- [ ] **Step 3: 做最小去重与收尾清理**

```markdown
<仅删除残留重复段落、补最少的文档跳转语句，不新增大段新正文；确保每个拆出章节只在唯一目标文档出现>
```

- [ ] **Step 4: 运行最终验证**

Run: `python3 -m pytest tests/unit/test_developer_docs_split.py -q`
Expected: PASS

Run: `python3 -m pytest tests/unit -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/developer/strategy.md docs/developer/control.md docs/developer/vision.md tests/unit/test_developer_docs_split.py
git commit -m "docs(developer): deduplicate split documentation"
```
