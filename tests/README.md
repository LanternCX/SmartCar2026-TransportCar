# 测试说明

当前仓库的正式测试体系由本地自动测试组成，用于主机侧快速回归。

- `tests/unit/`：主机侧行为测试与回归测试
- `tests/unit/core/`：共享底盘与诊断层测试
- `tests/unit/entry/`：入口、启动与角色分流测试
- `tests/unit/runtime/`：角色运行时行为与装配测试
- `tests/unit/command/`：串口正式入口边界测试
- `tests/unit/vision/`：车端视觉速度解析与辅助状态测试
- `tests/contract/serial_protocol/`：协议字段、报文格式与运行时协议契约测试

## 本地命令

```bash
python3 -m pytest tests/unit -q
python3 -m pytest tests/contract/serial_protocol -q
python3 -m pytest tests/unit tests/contract/serial_protocol -q
```

## 板端确认

板端确认通过用户与 AI 的对话协作完成，侧重记录操作步骤、现场现象、结果判断与复盘要点。

## 本仓库 TDD 循环

1. 先写失败的本地自动测试。
2. 确认失败原因与预期一致。
3. 编写最小实现。
4. 重新运行测试直到通过。
5. 在通过前提下重构。
