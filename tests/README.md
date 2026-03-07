# 测试分层

本仓库采用分层 TDD 验证模型，在不破坏运行时代码结构的前提下，把主机侧快回归和板级留证分开管理。

- `tests/unit/`：纯逻辑与确定性模块测试
- `tests/contract/`：基于 fake context / fake UART 的协议与行为契约测试
- `tests/hil/`：真实板级验证场景、观测脚本和验收记录

## 本地命令

```bash
python3 -m pytest tests/unit -q
python3 -m pytest tests/contract -q
python3 -m pytest tests/unit tests/contract -q
```

## 设备阶段

主机侧 `pytest` 之外，当前仓库补充了一条可脚本化的 Stage 3 设备观测链路：

```bash
python3 tools/run_device_observe.py --port /dev/cu.usbmodem1101
```

该命令会通过 `mpy-cli` 上传临时探针、运行短时观测、读取 `OBSERVE ...` 输出并在结束后删除远端探针文件。

## 本仓库 TDD 循环

1. 先写失败的 `unit` / `contract` 测试。
2. 确认失败原因与预期一致。
3. 编写最小实现。
4. 重新运行测试直到全绿。
5. 在全绿前提下重构。

对于硬件耦合行为，继续用 `unit/contract` 做快速回归，并将真实板证据记录到 `tests/hil/`。
