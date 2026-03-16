---
name: code-standards
description: Use when writing or reviewing SmartCar Python code, especially when architecture boundaries, coupling, state ownership, MicroPython constraints, and maintainability must stay healthy.
---

# Overview
统一 SmartCar 项目代码规范与架构边界, 保证代码在 RT1021 + MicroPython 约束下可维护, 可扩展, 可验证。

# When to Use
- 新增或重构任何 Python 模块（`services/`、`control/`、`hardware/`、`filters/` 等）
- 评审 PR, 判断代码是否符合项目质量基线
- 处理模块职责不清, 耦合过高, 过度设计, 隐式协议或跨层依赖等架构问题

# Core Rules
- 目标平台: MicroPython（RT1021）, 本地开发兼容 Python 3.8+
- 类型提示必须完整, 避免 `Any`, 返回值类型要显式
- 运行时代码默认不要依赖 `typing` 模块, 如需类型辅助, 优先使用内建类型标注, 字符串前向引用或不影响板端导入的兼容写法, 避免板端导入失败
- 注释与文档字符串统一使用中文
- 文档注释统一采用 Doxygen 风格, 默认使用 `@brief`, 按需补充 `@param`, `@return`, `@note`, `@warning`
- 注释与文档字符串中的标点使用半角符号, 且标点后需跟一个空格, 例如 `你好, 世界`
- 单行注释行尾不加句号, 逗号, 分号, 冒号等收尾标点
- 对复杂流程, 状态机分支, lazy 装配, 兼容桥接和非显然控制逻辑, 应补充充分的中文块注释帮助阅读
- 函数, 类和模块必须有中文 Doxygen 文档注释, 说明输入, 输出, 副作用和关键约束
- 行数门禁按非注释代码行计算, 文档注释, 块注释, 单行注释和空行不计入
- 当一个领域模块需要拆成 2 个以上内部实现文件时, 必须优先改为包目录加 `__init__.py`, 不得继续新增共同前缀平铺模块
- 禁止使用共同前缀平铺文件模拟命名空间, 例如 `foo_a.py`, `foo_b.py`, `foo_c.py`; 应改为 `foo/` 分包
- 魔法数字集中到 `config/params.py`
- 禁止静默失败, 只捕获预期异常并保留上下文

# Architecture Layers
- `hardware/`: 硬件驱动与总线访问, 不放业务逻辑
- `control/`: PID, 运动学, 轨迹, 姿态估计与底盘控制算法
- `filters/`: 独立可复用的滤波算法
- `services/`: 编排层, 连接硬件, 控制与领域子系统
- `vision/` 或独立领域包: 视觉协议, 状态机和视觉领域转换逻辑, 不应混入服务编排细节
- `storage/`: 持久化层（参数读写）
- `config/`: 配置与常量集中管理
- `utils/`: 通用纯函数工具

# Dependency Rules
- 允许: `services -> control/filters/hardware/storage/config/utils`
- 允许: `services -> vision` 或其他独立领域包
- 允许: `control -> filters/config/utils`
- 允许: `filters -> config/utils`
- 允许: `hardware -> config/utils`
- 允许: `vision -> config/utils`
- 禁止: 下层依赖上层（如 `hardware` 导入 `services`）
- 禁止: 循环依赖与跨层跳跃调用

# Architecture Health Rules
- 一个运行时状态只能有一个主拥有者, 禁止多个模块共享读写同一状态
- 模块协作必须通过显式接口, 受控数据结构或明确协议完成, 禁止依赖跨模块私有字段协议
- `services/` 只负责编排, 不承载底层算法细节, 设备访问细节或隐藏状态机
- command handler, query handler, facade 和 adapter 只能调用受控上下文接口, 不得直接读写宿主对象内部字段或临时属性
- import-time 自动注册必须 fail-fast, 可观测, 可验证, 禁止静默吞错, 延迟失败或部分失败后继续运行
- 发现 God object, 隐式上下文协议, 状态双写或职责漂移时, 优先拆分状态所有权和协作边界, 不要继续堆补丁
- diagnostics 只能只读聚合 owner 状态, 不得缓存第二份运行时状态
- command / query 装配默认应显式延迟加载, 不得回退到 import-time 全量注册

# Memory Budget Gate
- 对 `TransportCar`、运行时 owner、诊断 facade、命令装配和板端 probe 的改动, review 一号目标是最小内存占用指标, 不是结构整洁度
- 新增常驻对象必须说明 owner、阶段、A / B / C / D / E 分类、触发条件和必要性
- import-time 禁止目录扫描、自动发现、自动注册和重型单例初始化
- 模块级可变运行时全局状态属于阻断项
- 可延迟功能若被重新放回构造期无条件初始化, 直接视为不通过
- 热路径新增大字符串拼接、大临时容器或无解释动态分配时, 必须提供必要性证明
- 结构更清晰但内存指标未改善, 不算有效重构

# Anti-Overdesign Rules
- 没有 2 个以上真实消费者时, 不要引入通用框架式抽象
- 不要为了“未来可能扩展”提前引入事件总线, 插件系统或多层适配器链
- 新增抽象必须由当前需求, 当前复杂度或当前复用压力证明, 不能用假设中的未来变化作主要理由
- 优先简单对象边界和可追踪数据流, 不为表面解耦付出过高抽象税
- 若新增抽象只是在更多文件之间搬运复杂度, 但没有减少理解成本或测试成本, 则视为过度设计

# Refactor Triggers
- 单函数超过 50 行: 优先拆分
- 单模块超过 300 行: 按职责拆分
- 单一领域出现 2 个以上共同前缀平铺文件: 优先收拢为分包
- 同类重复逻辑出现 3 次以上: 提炼公共函数
- 业务编排混入驱动层或算法层: 立即上移到 `services/`
- 单对象同时承担协议解析, 状态管理, 硬件访问和控制算法: 视为 God object, 必须重构
- 单类同时持有过多运行时状态, 过多公开协作入口或跨越多个子系统决策: 即使文件未超行数, 也视为 God object 候选
- handler 或 helper 直接读写宿主 `_private` 字段: 视为封装破坏, 必须收口到显式接口

# Review Checklist
- 代码是否在正确分层目录
- 是否存在上层反向依赖或循环依赖
- 是否满足类型提示, 中文文档和异常处理要求
- 是否将参数和阈值集中到 `config/params.py`
- 是否满足 5ms 控制周期下的性能约束
- 是否存在状态单一所有权不明, 状态双写或状态泄漏
- 是否通过私有字段, 临时属性或隐式上下文协议耦合多个模块
- 是否为了未来假设需求引入了没有现实收益的抽象
- 是否把算法细节, 设备细节或领域状态继续堆进编排层
- 是否把 import-time 副作用当作默认装配方式, 且缺少失败可观测性
- 是否给出了 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle` 和 `diag_survival` 证据
- 是否说明了新增常驻对象为什么属于 A / B 类, 而不是 C / D 类

# Review Output Requirements
- 不要只给出“风格还可以”或“目录基本正确”这类表面结论
- 必须明确指出职责边界, 状态归属, 耦合方式和抽象成本是否健康
- 发现架构问题时, 要说明问题所在层级, 影响范围和更简单的替代方案
- 评审建议优先追求简单, 清晰, 可测试和可维护, 不以理论完美替代工程可控性
- 必须直接回答当前改动是否满足最小内存占用指标, 并给出对应证据

# Command Registration Pattern
- 命令接口仍可保留在受控命令子系统中, 但 handler 必须通过显式上下文接口工作
- 不新增对 `TransportCar._finalize_route(...)` 或宿主私有字段的直接耦合
- 若仓库仍保留自动发现注册, 任何修改都必须保证注册失败可见, 注册结果可验证

# Git Policy
- 本项目 Git 规范的唯一来源是 `.agents/skills/git-workflow/SKILL.md`
- 不要使用 superpowers 自带的 git workflow 作为本项目规范

# Deliverables
- 符合本规范的代码或重构结果
- 关键验证步骤与结果记录
- 如涉及架构调整, 提供简短变更说明（职责, 依赖, 影响）
