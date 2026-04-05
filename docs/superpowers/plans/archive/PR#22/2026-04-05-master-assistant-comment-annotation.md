# 主辅车目录注释补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `src/master/` 与 `src/assistant/` 下除 `test/`、`__pycache__/` 外的全部目标文件补齐符合仓库规范的注释, 显式排除 `src/legacy/`, 让 review 时可以快速看清链路结构、职责分层和关键设计意图。

**Architecture:** 先建立可执行的注释覆盖检查, 再按“入口与主链 -> 子模块 -> 脚本与参数”顺序分批补注释。注释本身不改运行行为, 但执行流程仍遵守 TDD: 先写失败的结构性检查, 再补注释让检查通过, 最后做抽样复核。

**Tech Stack:** Python, pytest, pathlib, ast, 仓库现有 `master` / `assistant` 目录结构, 中文 Doxygen 风格注释规范。

**执行约束:** 仅处理 `src/master/` 与 `src/assistant/`; 显式排除 `src/legacy/`、两个目录下的 `test/` 与全部 `__pycache__/`。SDD 执行时每次只派发一个任务组, 每组完成后先看测试结果, 再抽样看注释是否真的帮助结构 review。

---

### Task 1: 建立注释覆盖检查基线

**Files:**
- Create: `tests/unit/test_comment_annotation_layout.py`
- Modify: `docs/superpowers/plans/2026-04-05-master-assistant-comment-annotation.md`
- Reference: `docs/superpowers/specs/2026-04-05-master-assistant-comment-annotation-design.md`
- Reference: `.agents/skills/using-rules/references/comment-rules.md`

- [ ] Step 1: 列出 `src/master/` 与 `src/assistant/` 下需要纳入检查的目标文件, 明确排除 `src/legacy/`、两个目录下的 `test/`、`__pycache__/` 和二进制缓存
- [ ] Step 2: 先定义最低说明标准, 至少写清三类对象的完成条件: 源码文件必须有文件头定位; 对外方法、关键流程方法和理解成本高的方法必须有职责说明; 长流程文件必须存在帮助恢复阶段骨架的分段说明或等价说明
- [ ] Step 3: 再写失败的 pytest 检查, 让检查准确覆盖文件头、方法职责说明、脚本说明和参数文件说明这几类最低标准
- [ ] Step 4: 运行新增检查并确认它因当前注释不足而失败, 失败原因要能准确指出缺失项而不是测试本身错误
- [ ] Step 5: 若失败信息不够可执行, 先缩小或调整检查颗粒度, 直到它能稳定指出“哪类文件缺什么说明”
- [ ] Step 6: 固化第一轮红灯基线, 作为后续各批注释补全的统一验收入口

### Task 2: 补齐主车入口与主链骨架注释

**Files:**
- Modify: `src/master/__init__.py`
- Modify: `src/master/main.py`
- Modify: `src/master/app.py`
- Modify: `src/master/motion_runtime.py`
- Modify: `src/master/protocol.py`
- Modify: `src/master/runtime_params.py`
- Test: `tests/unit/test_comment_annotation_layout.py`

- [ ] Step 1: 基于 Task 1 的失败输出, 先补文件头说明, 让入口和主链文件一打开就能说明自身在主车链路中的位置
- [ ] Step 2: 为主车入口和主链文件中的对外方法、关键流程方法补 Doxygen 风格说明, 收口输入、输出和阶段职责
- [ ] Step 3: 为 `main.py`、`app.py`、`motion_runtime.py` 中的长流程补关键阶段注释, 只保留帮助理解骨架的分段说明
- [ ] Step 4: 对关键变量、常量和跨周期状态补贴身短注释, 满足仓库显式注释规则但不展开成逐行翻译
- [ ] Step 5: 运行注释覆盖检查, 确认主车入口与主链相关失败项转绿

### Task 3: 补齐主车子模块、脚本与参数说明

**Files:**
- Modify: `src/master/config.py`
- Modify: `src/master/ctrl/__init__.py`
- Modify: `src/master/ctrl/attitude.py`
- Modify: `src/master/ctrl/filters.py`
- Modify: `src/master/ctrl/ident.py`
- Modify: `src/master/ctrl/kinematics.py`
- Modify: `src/master/ctrl/pid.py`
- Modify: `src/master/ctrl/storage.py`
- Modify: `src/master/hw/__init__.py`
- Modify: `src/master/hw/encoders.py`
- Modify: `src/master/hw/imu.py`
- Modify: `src/master/hw/motors.py`
- Modify: `src/master/hw/uart.py`
- Modify: `src/master/state/__init__.py`
- Modify: `src/master/vision/__init__.py`
- Modify: `src/master/vision/decision.py`
- Modify: `src/master/vision/ingress.py`
- Modify: `src/master/vision/parser.py`
- Modify: `src/master/vision/state_machine.py`
- Modify: `src/master/script/__init__.py`
- Modify: `src/master/script/calibrate_gyro.py`
- Modify: `src/master/script/inspect_attitude.py`
- Modify: `src/master/script/pid_identify.py`
- Modify: `src/master/gyro_offset.txt`
- Modify: `src/master/ident_params.txt`
- Test: `tests/unit/test_comment_annotation_layout.py`

- [ ] Step 1: 按控制、硬件、状态、视觉、脚本、参数六组逐批补文件头说明, 保证每个文件先有清晰定位
- [ ] Step 2: 为各组里的关键类、函数和状态字段补职责说明, 重点解释模块边界、上下游关系和保留原因
- [ ] Step 3: 对长流程函数补关键阶段注释, 对简单适配函数只补最小必要说明, 避免风格失衡
- [ ] Step 4: 为脚本和参数文件采用设计文档约定的统一说明形态, 不强行把参数文本改写成不自然的 Doxygen 文档
- [ ] Step 5: 运行注释覆盖检查, 确认主车目录整体转绿

### Task 4: 补齐辅车入口与主链骨架注释

**Files:**
- Modify: `src/assistant/__init__.py`
- Modify: `src/assistant/main.py`
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/protocol.py`
- Modify: `src/assistant/runtime_params.py`
- Modify: `src/assistant/status.py`
- Modify: `src/assistant/safety.py`
- Test: `tests/unit/test_comment_annotation_layout.py`

- [ ] Step 1: 为辅车入口、运行时、状态回包和安全边界文件补文件头说明, 明确它们与主车对应层的相似点和职责差异
- [ ] Step 2: 为辅车对外方法和关键流程方法补 Doxygen 风格说明, 强调命令接收、执行推进和状态回包的链路责任
- [ ] Step 3: 为 `main.py`、`app.py`、`motion_runtime.py` 的长流程补关键阶段注释, 让 review 时先看到链路骨架
- [ ] Step 4: 为关键状态字段、超时相关常量和安全控制变量补贴身短注释
- [ ] Step 5: 运行注释覆盖检查, 确认辅车主链相关失败项转绿

### Task 5: 补齐辅车子模块、脚本与参数说明

**Files:**
- Modify: `src/assistant/config.py`
- Modify: `src/assistant/ctrl/__init__.py`
- Modify: `src/assistant/ctrl/attitude.py`
- Modify: `src/assistant/ctrl/filters.py`
- Modify: `src/assistant/ctrl/ident.py`
- Modify: `src/assistant/ctrl/kinematics.py`
- Modify: `src/assistant/ctrl/pid.py`
- Modify: `src/assistant/ctrl/storage.py`
- Modify: `src/assistant/hw/__init__.py`
- Modify: `src/assistant/hw/encoders.py`
- Modify: `src/assistant/hw/imu.py`
- Modify: `src/assistant/hw/motors.py`
- Modify: `src/assistant/hw/uart.py`
- Modify: `src/assistant/state/__init__.py`
- Modify: `src/assistant/script/__init__.py`
- Modify: `src/assistant/script/calibrate_gyro.py`
- Modify: `src/assistant/script/inspect_attitude.py`
- Modify: `src/assistant/script/pid_identify.py`
- Test: `tests/unit/test_comment_annotation_layout.py`

- [ ] Step 1: 先补文件头说明, 再按控制、硬件、状态、脚本四组统一补职责边界说明
- [ ] Step 2: 为关键类、函数和跨周期状态补职责与协作说明, 保持与主车同层文件的表达方式尽量对齐
- [ ] Step 3: 对复杂流程补关键阶段注释, 对简单函数保留最短必要说明
- [ ] Step 4: 检查辅车脚本说明是否与主车脚本口径一致, 避免同类文件写成两套风格
- [ ] Step 5: 运行注释覆盖检查, 确认辅车目录整体转绿

### Task 6: 收口检查规则并做全量验证

**Files:**
- Modify: `tests/unit/test_comment_annotation_layout.py`
- Verify: `src/master/**/*.py`
- Verify: `src/master/**/*.txt`
- Verify: `src/assistant/**/*.py`
- Verify: `src/assistant/**/*.txt`

- [ ] Step 1: 根据前几轮补注释的实际情况, 收紧或校正检查规则, 避免遗漏目标文件或错误要求参数文本使用不适合的形式
- [ ] Step 2: 运行注释覆盖检查全量用例, 确认目标文件全部达到最低说明标准
- [ ] Step 3: 运行现有主机侧相关单测抽样回归, 确认补注释没有引入语法或导入问题
- [ ] Step 4: 抽样人工复核主车与辅车各至少 3 个关键文件, 检查是否真的达到了“快速看懂结构和设计”的目标, 而不是只满足形式检查
- [ ] Step 5: 整理执行结果, 记录仍需人工判断的边角文件, 再进入最终 review
