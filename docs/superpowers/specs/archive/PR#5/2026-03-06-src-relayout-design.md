# 源码与脚手架分离设计文档

## 背景

当前仓库根目录同时包含业务代码目录与多类运行脚本,导致工作区边界不清晰。目标是将业务代码统一归档到 `src/`,并将根目录脚本归档到 `src/script/`,同时保留可部署性与测试可运行性。

## 目标

1. 业务代码迁移到 `src/`。
2. 根目录脚本迁移到 `src/script/`。
3. `boot.py` 特殊放置在 `src/boot.py`。
4. 保持现有导入风格（例如 `from control...`）,通过路径配置兼容测试与类型检查。
5. 部署流程切换为以 `src` 为源码根。

## 约束与范围

- 不修改业务功能语义,仅做目录重构与路径适配。
- 不引入根目录兼容壳文件（用户明确要求彻底迁移）。
- 不调整分层架构边界：`services -> control/filters/hardware/storage/config/utils`。

## 设计决策

### 1) 目录重构

- 迁移目录：
  - `config/ -> src/config/`
  - `control/ -> src/control/`
  - `filters/ -> src/filters/`
  - `hardware/ -> src/hardware/`
  - `services/ -> src/services/`
  - `storage/ -> src/storage/`
  - `utils/ -> src/utils/`
- 迁移脚本：
  - `boot.py -> src/boot.py`
  - `calibrate_gyro.py -> src/script/calibrate_gyro.py`
  - `pid_identify.py -> src/script/pid_identify.py`
  - `remote_control.py -> src/script/remote_control.py`
  - `test.py -> src/script/test.py`
  - `yaw_sender.py -> src/script/yaw_sender.py`

### 2) 启动逻辑保持

- 保留拨码开关逻辑。
- 在 `src/boot.py` 中将 `execfile("pid_identify.py")` 与 `execfile("remote_control.py")` 调整为 `script/` 子路径。

### 3) 工具链与测试适配

- `.mpy-cli.toml` 设置 `source_dir = 'src'`。
- `tests/conftest.py` 将 `src` 注入 `sys.path`。
- `pyrightconfig.json` 将 `./src` 加入 `extraPaths`。
- `.mpyignore` 将脚本忽略项同步为 `script/test.py`。

## 风险与缓解

1. 风险：导入路径失效导致测试失败。
   - 缓解：先补失败测试验证布局,再迁移并立即跑 `unit + contract`。
2. 风险：启动脚本引用路径错误。
   - 缓解：显式修改 `src/boot.py` 的 `execfile` 目标并在部署预览中确认。
3. 风险：文档与实际路径不一致。
   - 缓解：更新关键文档中的脚本路径与目录树。

## 验收标准

- `python3 -m pytest tests/unit tests/contract -q` 全绿。
- `python3 -m pyright` 不新增错误。
- 根目录不再存在业务目录 `config/control/filters/hardware/services/storage/utils`。
- 根目录不再存在脚本 `calibrate_gyro.py/pid_identify.py/remote_control.py/test.py/yaw_sender.py/boot.py`。
- 对应文件全部位于 `src/` 与 `src/script/`。
