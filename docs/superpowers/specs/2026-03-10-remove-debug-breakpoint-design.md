# 删除 debug 断点机制设计文档

## 背景

当前 `TransportCar` 中存在一套基于 `debug=1` 串口放行的断点等待机制。该机制会暂停主循环、清零电机输出并等待人工恢复。现决定彻底删除这套机制, 后续若需要新的调试暂停能力, 再重新设计。

## 目标

1. 从运行时代码中彻底移除 debug 断点等待机制。
2. 保留正常日志能力, 尤其是视觉状态迁移日志。
3. 删除与旧断点机制强绑定的单元测试和旧计划文档。
4. 保持查询、日志和控制主循环语义清晰, 不留下半残留兼容壳。

## 非目标

- 不设计新的断点/暂停机制。
- 不改变现有全局日志系统的等级、过滤、颜色和 `?log` 行为。
- 不修改与 debug 断点无关的控制逻辑。

## 方案

采用硬删除方案：

- 删除 `src/services/transport_car.py` 中 `debug()` 及其配套辅助函数、状态字段和相关分支。
- 删除 `tests/unit/services/test_transport_car_debug_breakpoint.py`。
- 调整 `tests/unit/services/test_transport_car_vision_integration.py`, 去掉“不会触发断点”的断言, 保留“视觉日志仍正常输出”的验证。
- 删除旧计划文档 `docs/superpowers/plans/2026-03-09-vision-transition-debug-breakpoint.md`。

## 影响范围

- `src/services/transport_car.py`
- `tests/unit/services/test_transport_car_debug_breakpoint.py`
- `tests/unit/services/test_transport_car_vision_integration.py`
- `docs/superpowers/plans/2026-03-09-vision-transition-debug-breakpoint.md`

## 测试策略

- 先写 / 调整失败测试, 锁定“旧 debug 断点接口不存在, 视觉日志仍可输出”。
- 运行聚焦单测验证删除结果。
- 再跑 `tests/unit tests/contract` 全量主机测试, 确认无回归。

## 验收标准

- 运行时代码中不再存在 `debug()` 断点等待机制及其辅助状态。
- 不再存在专门覆盖该机制的单元测试文件。
- 视觉状态迁移日志仍通过全局 logger 输出。
- 主机侧相关测试和全量测试通过。
