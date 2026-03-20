# Stage 2 Smoke 打包设计文档

## 背景

当前 Stage 2 相关实现分散在 `src/services/stage2_smoke.py`、`src/services/stage2_smoke_lite.py`、`src/services/stage2_smoke_full.py` 三个根目录文件中。虽然行为上已经可用, 但这类目录平铺会继续放大 `services/` 根目录的杂糅感, 与当前 transport runtime 解耦方向不一致。

用户明确要求: Stage 2 也要打包, 不要继续直接挂在 `src/services/` 根目录下。

## 目标

1. 将 Stage 2 smoke 相关实现收拢到 `src/services/stage2_smoke/` 子包。
2. 保持对外公共入口 `services.stage2_smoke` 不变, 避免无意义地扩大调用点改动面。
3. 保持板端 probe, lite fallback, full smoke 和现有测试行为不变。
4. 不引入兼容壳文件, 不保留旧的 `stage2_smoke_lite.py` / `stage2_smoke_full.py` 根目录散文件。

## 非目标

1. 不修改 Stage 2 smoke 的输出协议。
2. 不改变 full / lite fallback 条件。
3. 不扩展新的设备调试功能。

## 目标结构

```text
src/services/
  stage2_smoke/
    __init__.py
    entry.py
    lite.py
    full.py
```

## 设计要点

### 公共导入面

- 保留 `import services.stage2_smoke as stage2_smoke_module` 作为稳定入口。
- `src/services/stage2_smoke/__init__.py` 只做受控导出, 将当前测试和调用方需要的符号从 `entry.py` 暴露出来。
- 这样 `tools/` 和测试无需整体切换到深层模块路径, 降低重构噪声。

### 包内职责

- `entry.py`: 保存当前 `stage2_smoke.py` 的入口编排逻辑, 包括 token 常量, full/lite fallback, 结果格式化和 `main()`。
- `lite.py`: 保存当前 lite 模式 helper, 最小上下文和 query smoke。
- `full.py`: 保存 full 模式 helper, `TransportCar(diagnostic_mode=True)` 的最小安全 smoke。

### 板端导入约束

- `tools/stage2_smoke_probe.py` 继续避免 `from ... import ...` 形式, 保持 `__import__` + `sys.modules[...]` 模式, 以降低板端导入不稳定风险。
- probe 直接导入稳定公共入口 `services.stage2_smoke`, 不向真实调用方泄露 `lite.py` / `full.py` 内部布局。
- `main()` 和 `collect_stage2_summary()` 继续由包级公共面提供, 但板端 probe 只调用包级 `_collect_lite_transport_summary()`, 包内布局只作为实现细节。
- 现有关于 `gc.collect()` 先于 runtime import 的约束保持不变。

### 测试与验证

- 先改测试, 锁定新的包路径和文件布局。
- host 侧至少覆盖 `tests/unit/services/test_transport_car_diag_mode.py` 与 `tests/unit/tools/test_run_stage2_smoke.py`。
- 因为这次改动直接触及板端 probe 的真实导入路径, host 测试通过后还要补跑一次 `python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101`。

## 验收标准

1. `src/services/` 根目录不再存在 `stage2_smoke.py`、`stage2_smoke_lite.py`、`stage2_smoke_full.py` 散文件。
2. `services.stage2_smoke` 仍可作为外部公共入口使用。
3. probe 使用 `services.stage2_smoke` 成功导入, 且不暴露内部模块路径。
4. 目标单测通过, Stage 2 设备 smoke 通过。
