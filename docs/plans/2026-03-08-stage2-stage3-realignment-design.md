# Stage2/Stage3 职责纠偏设计

## 背景

当前仓库把 `stage3` 的自动脚本实现成了通过 `mpy-cli` 上传并执行临时探针的流程，这与当前开发目标不一致。

本次纠偏采用以下原则：

- `stage1` 继续负责主机侧 `unit/contract` TDD
- `stage2` 负责 USB / 裸片 smoke，目标是保证板端最小运行不报错
- `stage3` 不再定义为自动化测试，而是 `uart3` 人工调试流程
- `HIL` 负责把 `stage3` 的真机观察与结论沉淀为留证

## 设计目标

1. 让 AI 在板端阶段至少能把代码交付到“安全启动、短时运行不报错”的状态。
2. 避免把 `uart6` 从 OpenArt 通信链路中抢占出来做自动化调试。
3. 让 `stage3` 明确成为人和 AI 在环的调试协作，而不是误导性的自动通过判定。

## 设计结论

### Stage2

`stage2` 统一定义为自动化裸片 smoke：

- 通过 `mpy-cli` 连通设备并执行临时探针
- 在 `diagnostic_mode=True` 下初始化 `TransportCar`
- 短时执行主循环相关逻辑，确保不抛异常
- 构造关键诊断快照，确保运行期最小观测面可用
- 不验证具体控制逻辑正确性，不驱动大幅运动

### Stage3

`stage3` 统一定义为 `uart3` 人工调试流程：

- AI 提供调试步骤、建议查询项和故障归因思路
- 人在环通过 `uart3` 观察运行状态与交互结果
- 不再把 `stage3` 定义为自动 PASS / FAIL 的主机脚本

### HIL

`HIL` 继续作为最终留证层：

- 记录 `stage3` 的操作步骤
- 记录关键串口输出、现象和结论
- 输出 PASS / FAIL 结论

## 落地影响

- 现有 `tools/run_device_observe.py` 需要从“stage3 观测器”纠偏为“stage2 smoke runner”
- `tools/stage2_smoke_probe.py` 需要从“导入与注册检查”增强为“安全初始化 + 短时运行 + 快照构造”
- `tests/README.md`、`tests/hil/README.md`、`Readme.md` 需要同步调整叙事
- `git-workflow` 需要补充一条仓库约束：不要使用 superpowers 自带的 worktree 工作流
