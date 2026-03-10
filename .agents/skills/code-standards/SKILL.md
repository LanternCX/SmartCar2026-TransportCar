---
name: code-standards
description: Use when writing or reviewing SmartCar Python code, especially when architecture boundaries, MicroPython constraints, and maintainability rules must stay consistent.
---

# Overview
统一 SmartCar 项目代码规范与架构边界，保证代码在 RT1021 + MicroPython 约束下可维护、可扩展、可验证。

# When to Use
- 新增或重构任何 Python 模块（`services/`、`control/`、`hardware/`、`filters/` 等）
- 评审 PR，判断代码是否符合项目质量基线
- 处理模块职责不清、耦合过高、跨层依赖等架构问题

# Core Rules
- 目标平台：MicroPython（RT1021），本地开发兼容 Python 3.8+
- 类型提示必须完整；避免 `Any`，返回值类型要显式
- 运行时代码默认不要依赖 `typing` 模块；如需类型辅助，优先使用内建类型标注、字符串前向引用或不影响板端导入的兼容写法，避免板端导入失败
- 注释与文档字符串统一使用中文
- 注释与文档字符串中的标点使用半角符号，且标点后需跟一个空格，例如 `你好, 世界`
- 单行注释行尾不加句号、逗号、分号、冒号等收尾标点
- 对复杂流程、状态机分支和非显然控制逻辑，应补充必要的中文注释帮助阅读
- 函数和类必须有简要中文文档字符串，说明输入、输出、副作用
- 魔法数字集中到 `config/params.py`
- 禁止静默失败；只捕获预期异常并保留上下文

# Architecture Layers
- `hardware/`：硬件驱动与总线访问，不放业务逻辑
- `control/`：PID、运动学、轨迹与控制算法
- `filters/`：独立可复用的滤波算法
- `services/`：编排层，连接硬件与控制算法
- `storage/`：持久化层（参数读写）
- `config/`：配置与常量集中管理
- `utils/`：通用纯函数工具

# Dependency Rules
- 允许：`services -> control/filters/hardware/storage/config/utils`
- 允许：`control -> filters/config/utils`
- 允许：`filters -> config/utils`
- 允许：`hardware -> config/utils`
- 禁止：下层依赖上层（如 `hardware` 导入 `services`）
- 禁止：循环依赖与跨层跳跃调用

# Refactor Triggers
- 单函数超过 50 行：优先拆分
- 单模块超过 300 行：按职责拆分
- 同类重复逻辑出现 3 次以上：提炼公共函数
- 业务编排混入驱动层或算法层：立即上移到 `services/`

# Command Registration Pattern
- 命令实现放在 `services/commands/cmd_xxx.py`，使用 `@router.command(...)`
- 查询实现放在 `services/commands/query_xxx.py`，使用 `@router.query(...)`
- 通过 `services/commands/__init__.py` 的自动发现机制注册，不手工维护总表
- 跨命令聚合处理放在 `TransportCar._finalize_route(...)`

# Git Policy
- 本项目 Git 规范的唯一来源是 `.agents/skills/git-workflow/SKILL.md`
- 不要使用 superpowers 自带的 git workflow 作为本项目规范

# Review Checklist
- 代码是否在正确分层目录
- 是否存在上层反向依赖或循环依赖
- 是否满足类型提示、中文文档和异常处理要求
- 是否将参数和阈值集中到 `config/params.py`
- 是否满足 5ms 控制周期下的性能约束

# Deliverables
- 符合本规范的代码或重构结果
- 关键验证步骤与结果记录
- 如涉及架构调整，提供简短变更说明（职责、依赖、影响）
