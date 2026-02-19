---
name: code-standards
description: Enforce SmartCar Python code style, MicroPython compatibility, architecture health, and documentation quality.
---

# Purpose
保持代码库与 MicroPython 规范、项目模式、可维护架构和生产级文档保持一致。

# When to Use
- 编写新的 Python 模块或控制流程
- 重构服务层、控制算法、硬件驱动或工具函数
- 审查贡献的代码风格、安全性、可观察性和架构完整性

# Style & Structure Rules
- 目标平台：MicroPython on RT1021；兼容 Python 3.8+ 进行本地开发
- **类型提示强制使用**；优先使用显式返回类型；避免 `Any` 除非不可避免
- **所有代码注释和文档字符串必须使用中文**
- **所有函数、类必须包含文档字符串**，简要说明功能、参数、返回值和副作用
- 保持函数短小且单一职责；为重复代码块提取辅助函数
- 错误处理：捕获特定异常；记录上下文；避免静默失败
- 导入：stdlib → 第三方 → 本地；删除未使用的导入；避免循环导入
- 配置：优先使用 `config/params.py` 集中配置；避免魔法数字
- 架构：保持清晰的模块边界；追求高内聚低耦合以保持仓库的可维护性和可扩展性

# Architecture Principles
- **分层架构**：
  - `hardware/`：硬件驱动层，封装所有硬件接口
  - `control/`：控制算法层，实现 PID、运动学、轨迹规划等核心算法
  - `filters/`：滤波算法层，独立的信号处理模块
  - `services/`：业务逻辑层，协调硬件和控制算法
  - `utils/`：通用工具层，无依赖的纯函数工具
  - `config/`：配置管理层，集中所有可调参数
  - `storage/`：持久化层，处理参数的加载和保存

- **依赖规则**：
  - 上层可以依赖下层，下层不能依赖上层
  - 同层模块之间尽量减少依赖
  - 硬件层应该可独立测试和替换

- **命名规范**：
  - 文件名：小写下划线分隔（`transport_car.py`）
  - 类名：大驼峰（`TransportCar`）
  - 函数名：小写下划线分隔（`parse_command`）
  - 常量：全大写下划线分隔（`MAX_DUTY`）
  - 私有成员：单下划线前缀（`_internal_state`）

# MicroPython Compatibility
- 避免使用不支持的标准库（如 `asyncio`、`threading`）
- 使用 `machine`、`smartcar` 等 MicroPython 特定库
- 注意内存限制：避免大量动态分配，重用对象
- 浮点运算性能较低：关键路径考虑使用定点运算
- 字符串操作开销较大：减少字符串拼接和格式化

# Code Review Checklist
- 类型提示：所有函数参数和返回值都有类型注解
- 文档：所有公共接口都有中文文档字符串
- 注释：复杂逻辑有中文注释说明
- 配置：所有魔法数字都移到 `config/params.py`
- 错误处理：所有可能失败的操作都有适当的异常处理
- 资源管理：所有打开的资源都正确关闭（硬件接口、文件等）
- 性能：控制周期内的操作要高效（5ms 控制周期）
- 测试：关键算法有对应的测试或验证脚本
- 架构：新代码遵循分层架构，放在正确的目录

# Refactor Guardrails
- 保留公共行为和通信协议（串口命令格式）
- 不破坏配置 schema；如不可避免，添加迁移说明
- 保持控制周期稳定性；避免引入阻塞操作
- 维护硬件驱动的线程安全性

# Deliverables
- 符合上述标准的更新代码
- 测试说明（执行的命令和结果）
- 确认错误检查没有遗留问题
- 如果影响文档，交给 `doc-maintainer` skill
