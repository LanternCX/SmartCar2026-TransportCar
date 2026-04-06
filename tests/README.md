# 测试分层

本仓库采用分层 TDD 验证模型，在不破坏运行时代码结构的前提下，把主机侧快回归和板级留证分开管理。

- `tests/unit/`：主机侧快速回归测试
- `tests/hil/`：真实板级验证场景、观测脚本和验收记录

## 本地命令

```bash
python3 -m pytest tests/unit -q
```

## 设备阶段

主机侧 `pytest` 之外，设备阶段拆成两层：

- `stage2`：自动化裸片 smoke
- `stage3`：`uart3` 人工调试

`stage2` 命令：

```bash
python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101
```

该命令会通过 `mpy-cli` 上传临时探针，在 `diagnostic_mode=True` 下执行最小安全 smoke，并在结束后删除远端探针文件。

`stage3` 不再定义为自动脚本；其职责是让人和 AI 在 `uart3` 上观察、查询和归因运行期逻辑问题。

## 本仓库 TDD 循环

1. 先写失败的 `unit` / `contract` 测试。
2. 确认失败原因与预期一致。
3. 编写最小实现。
4. 重新运行测试直到全绿。
5. 在全绿前提下重构。

对于硬件耦合行为，继续用 `unit/contract` 做快速回归，并按 `stage1 -> stage2 -> stage3 -> HIL` 记录真实板证据。
