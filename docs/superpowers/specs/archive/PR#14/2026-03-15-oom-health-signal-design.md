# 轻量 OOM 观测设计

## 目标

为板端提供一个不会显著放大内存压力的 OOM 观测信号, 让 `?health` 能回答“最近有没有发生过 OOM”。

## 方案

- 在运行时对象上增加两个最小字段:
  - `oom_count`
  - `last_oom_stage`
- 先只接入 logger 路径中的 OOM:
  - `format`
  - `sink`
- `LogManager` 通过一个轻量回调上报 OOM, 不在回调里构造大字符串
- `DiagnosticsFacade.build_health_snapshot()` 暴露:
  - `oom_count`
  - `oom_stage`

## 约束

- 不新增复杂历史兼容层
- 不记录详细模块名或长文本, 避免观测本身增加分配压力
- 先只覆盖 logger OOM, 用最小改动回答“系统最近是否发生过 OOM”
