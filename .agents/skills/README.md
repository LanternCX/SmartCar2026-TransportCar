# SmartCar Project Skills

这个目录包含了 SmartCar2026-TransportCar 项目的开发技能指南，用于规范代码开发、架构设计和系统集成。

## Skills Overview

### 1. [skill-manager](./skill-manager/SKILL.md)
**用途**：技能库管理和演进

管理和维护所有技能指南，确保它们与项目当前的需求、架构标准和开发里程碑保持一致。

**何时使用**：
- 项目里程碑前后
- 发现技能覆盖不足时
- 技能之间存在冲突或过时时

---

### 2. [code-standards](./code-standards/SKILL.md)
**用途**：代码规范和质量标准

定义 Python/MicroPython 代码风格、命名规范、文档要求和最佳实践。

**何时使用**：
- 编写新代码
- 代码审查
- 重构现有代码

**核心原则**：
- 类型提示强制使用
- 所有注释和文档使用中文
- MicroPython 兼容性
- 高代码可读性

---

### 3. [architecture-guardian](./architecture-guardian/SKILL.md)
**用途**：架构设计和模块组织

确保代码库保持高内聚低耦合的架构特性，清晰的分层设计和模块职责。

**何时使用**：
- 添加新功能模块
- 重构现有架构
- 架构评审

**核心架构**：
```
services/   (业务逻辑层)
   ↓
control/    (控制算法层)    filters/   (滤波算法层)
   ↓                          ↓
hardware/   (硬件驱动层)
   ↓
config/     (配置管理)    utils/     (工具函数)
   ↓
storage/    (持久化层)
```

---

### 4. [control-system](./control-system/SKILL.md)
**用途**：控制算法开发和调优

规范 PID 控制、运动学、轨迹规划等控制算法的开发、调试和优化流程。

**何时使用**：
- 实现新控制算法
- 调试控制不稳定
- 优化控制性能
- PID 参数调优

**核心内容**：
- 控制系统架构（位置环 → 速度环 → 电机）
- PID 调参指南
- 运动学和里程计
- 滤波器设计
- 常见问题诊断

---

### 5. [hardware-integration](./hardware-integration/SKILL.md)
**用途**：硬件驱动开发和集成

规范硬件驱动的开发流程，处理实时系统约束和硬件接口问题。

**何时使用**：
- 添加新硬件外设
- 调试硬件通信问题
- 优化实时性能
- 处理硬件异常

**核心内容**：
- 硬件抽象层设计
- UART/PWM/Encoder/IMU 接口
- 5ms 实时控制约束
- 性能优化策略
- 硬件调试方法

---

### 6. [git-workflow](./git-workflow/SKILL.md)
**用途**：Git 分支管理和提交规范

规范 Git Flow 工作流和 Angular 提交信息格式，确保版本历史清晰可追溯。

**何时使用**：
- 创建新功能或修复分支
- 提交代码变更
- 合并分支或发布版本

**核心内容**：
- Git Flow 分支策略（master / dev / feature / fix / hotfix / release）
- Angular 提交信息规范（英文、type/scope/subject 格式）
- 语义化版本标签
- 提交前检查清单

---

## Quick Start

### 新功能开发流程
1. **创建分支**：遵循 [git-workflow](./git-workflow/SKILL.md) 从 `dev` 切出 `feature/` 分支
2. **架构设计**：参考 [architecture-guardian](./architecture-guardian/SKILL.md) 确定模块位置和职责
3. **代码编写**：遵循 [code-standards](./code-standards/SKILL.md) 的规范
4. **控制算法**：参考 [control-system](./control-system/SKILL.md) 实现和调优
5. **硬件集成**：参考 [hardware-integration](./hardware-integration/SKILL.md) 开发驱动
6. **提交合并**：遵循 [git-workflow](./git-workflow/SKILL.md) 提交信息规范并合并回 `dev`

### 问题诊断流程
1. **硬件问题**：查看 [hardware-integration](./hardware-integration/SKILL.md) 常见问题
2. **控制问题**：查看 [control-system](./control-system/SKILL.md) 常见问题
3. **架构问题**：检查是否违反 [architecture-guardian](./architecture-guardian/SKILL.md) 原则
4. **代码质量**：对照 [code-standards](./code-standards/SKILL.md) 检查清单

---

## Design Philosophy

### 高内聚低耦合
- 每个模块职责单一清晰
- 模块间通过接口交互
- 避免跨层调用和循环依赖

### 可测试性
- 硬件层可独立测试
- 控制算法可离线验证
- 业务逻辑可单元测试

### 可扩展性
- 新功能容易添加
- 配置参数集中管理
- 接口设计预留扩展空间

### 可维护性
- 代码自文档化
- 中文注释详细
- 架构清晰易懂

---

## Contributing

### 更新技能指南
如果发现技能指南不足或过时：
1. 参考 [skill-manager](./skill-manager/SKILL.md) 的更新流程
2. 创建或修改相应的 SKILL.md 文件
3. 更新本 README.md 中的概述
4. 提交 PR 说明更新原因

### 技能指南命名
- 目录名：小写-连字符（kebab-case）
- 文件名：SKILL.md（大写）
- 技能名：描述性英文名称

---

## References

- [项目 README](../../Readme.md)：项目整体介绍和快速开始
- [参数配置](../../config/params.py)：所有可调参数定义
- [控制核心](../../services/transport_car.py)：车模核心实现
- [通信协议](../../Readme.md#遥控协议)：串口命令格式

---

## Changelog

### 2026-02-19
- 初始创建技能库
- 添加 5 个核心技能指南：
  - skill-manager：技能库管理
  - code-standards：代码规范
  - architecture-guardian：架构守护
  - control-system：控制系统
  - hardware-integration：硬件集成
- 添加 git-workflow：Git Flow 分支策略和 Angular 提交规范
