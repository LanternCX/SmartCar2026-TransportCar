# diagnostics 包内日志模块改名设计文档

## 背景

当前 `src/diagnostics/` 目录下只有日志相关模块, 但文件名仍使用 `log_` 前缀：`log_manager.py`、`log_format.py`、`log_sink.py`。在已位于 `diagnostics/` 包内的前提下, 这些前缀带来重复命名, 可读性一般。

## 目标

1. 去掉 `diagnostics` 包内文件名的重复 `log_` 前缀。
2. 保持现有日志能力、导入语义和测试行为不变。
3. 只做最小重命名和导入路径调整, 不顺手扩展包导出接口。

## 方案

采用最小改名方案：

- `src/diagnostics/log_manager.py` -> `src/diagnostics/manager.py`
- `src/diagnostics/log_format.py` -> `src/diagnostics/format.py`
- `src/diagnostics/log_sink.py` -> `src/diagnostics/sink.py`

同步修改所有导入路径, 但不改类名、函数名和行为。

## 测试策略

- 先调整测试导入路径, 让测试因模块不存在而失败。
- 再执行最小重命名和导入修正。
- 跑聚焦测试和全量 host 测试确认无回归。

## 验收标准

- `src/diagnostics/` 下不再有 `log_*.py` 文件。
- 所有原日志功能与测试保持通过。
- 外部模块统一改为使用 `diagnostics.manager`、`diagnostics.format`、`diagnostics.sink`。
