---
name: using-rules
description: Use when implementing or refactoring code in this repository and needing to check project rules, constraints, or domain knowledge.
---

# Using Rules

## 概览

这是当前仓库实现前与实现中的规则入口。
主入口只做最短路由, 具体规则按执行场景分到少量 reference 页, 避免一次加载过多无关上下文。

## 何时使用

- 开始实现或重构仓库代码前
- 不确定当前改动需要遵守哪些项目规则时
- 触及硬件、协议、控制、视觉、内存、文档或注释语义时

## 最短阅读路径

1. 先判断任务是否依赖项目方向或阶段目标。
   - 需要方向背景时, 先读 `docs/developer/strategy.md`。
   - 只做局部实现且方向已明确时, 不强制展开整套方向文档。
2. 所有代码实现与重构任务先读 `references/implementation-core.md`。
3. 按触发条件追加读取对应 reference, 不要把全部 reference 当成默认必读。

## Reference 路由

- 通用实现硬门禁、目录边界、TDD、验证、板端路径和内存约束 -> `references/implementation-core.md`
- 硬件事实、串口链路、协议入口、坐标语义和联调事实确认 -> `references/hardware-protocol.md`
- 控制链、角色运行入口、视觉速度输入、调参与诊断顺序 -> `references/control-vision-runtime.md`
- 项目文档、Skill 文档、代码注释和文档字符串写作规则 -> `references/docs-and-comments.md`

## 必须停下确认的情况

- 仓库正文没有给出具体引脚、串口、电平、接线或设备行为事实
- 协议字段、坐标方向、车体参考系或视觉输入职责出现冲突
- 改动不能直接服务当前完赛主线, 或会把当前任务扩成另一条主线
- 改动触及 `TransportCar`、控制执行内核、角色运行入口、诊断面或板端 probe, 但内存与板端验证边界说不清

## 边界

- `using-rules` 只服务实现前和实现中的规则查询。
- 完成前收口评审使用 `project-extension-requesting-code-review`。
- `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 的归档整理使用 `reference-sync`。
