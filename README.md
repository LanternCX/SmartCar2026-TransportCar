# 2025 智能车蚂蚁搬家组 - 搬运车模代码

## 项目定位

本仓库维护 RT1021 搬运车模控制代码，覆盖主辅双车协同、底盘控制、主辅通信、本地视觉链路和主机侧测试。

维护时以代码、注释和行为测试作为事实来源。文档只补充代码难以表达的项目方向、外部约定、题面来源和可复用协作记忆。

## 主要入口

- 启动入口: [src/main.py](src/main.py)
- 运行脚本: [src/script/remote_control.py](src/script/remote_control.py)
- 共享底盘: [src/core/runtime.py](src/core/runtime.py)
- 主车角色: [src/vision/master/](src/vision/master/)
- 辅车角色: [src/vision/assistant/](src/vision/assistant/)
- 串口协议工具: [src/protocol/](src/protocol/)
- 行为测试: [tests/](tests/)

## 附属仓库

- OpenART 视觉仓库位于 `../SmartCar2026-Vision`。
- 主机端侧手柄控制上位机位于 `../SmartCar2026-Controller`。
- 项目规则、题面材料、协作文档和长期开发文档以本仓库为准。

## 文档入口

文档按“短索引 -> 代码 -> 测试 -> memory”的顺序使用，不维护代码事实的长篇镜像。

- [项目方向](docs/developer/strategy.md)
- [电控与运行入口](docs/developer/control.md)
- [串口通信协议](docs/developer/protocol.md)
- [状态机说明](docs/developer/state.md)
- [视觉职责](docs/developer/vision.md)
- [赛题资料](docs/problem_statement/README.md)
- [协作记忆](docs/superpowers/memory/)
- GitHub issue 和 PR 记录用于任务推进与历史追溯。

## 本地开发

```bash
uv sync --group test
uv run --group test python -m pytest tests/unit tests/contract/serial_protocol -q
```

板端工具通过独立依赖组进入环境：

```bash
uv sync --group board
uv run --group board mpy-cli plan
bash build.sh
```
