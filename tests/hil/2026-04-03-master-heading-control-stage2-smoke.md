# 2026-04-03 主车航向控制稳定性 Stage 2 Smoke 留证

## 状态

- 当前状态: 未执行, 待设备连接后执行
- 当前基线提交: `c95f10c`
- 当前工作区状态: 存在未提交的 `docs/superpowers/memory/**` 与 `.agents/skills/using-rules/references/implementation-rules.md` 改动, 不属于本次主车控制实现提交
- legacy 对照版本标识: 待补充具体提交号, 当前参考 `src/legacy/control/motion_planner.py` 与 `src/legacy/control/pid_controller.py`
- 留证路径: `tests/hil/2026-04-03-master-heading-control-stage2-smoke.md`
- 附件预留路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage2-smoke/`
- 执行限制: 本页只记录设备连接、上传、启动、smoke 和最小查询, 不记录真实动作手感结论

## Stage 2 分工

- 只负责设备连接、上传、运行与最小 smoke
- 只确认模块可导入、主循环可启动、最小查询可复核
- 不在本页记录人工动作表现、手感对比或 legacy 行为归因

## 当前版本改动前基线

- 基线状态: 未执行, 待设备联调后补齐
- 要求: 先记录当前版本基线, 再记录后续实现版本结果
- 说明: 每个场景至少 3 次, 不记录伪数据

## 观察场景

### 场景 1: 主动旋转后松手

- 预期现象: 设备可稳定启动并保持最小查询可用, 为后续 Stage 3 人工动作对比提供可信运行前提
- Stage 2 实测: 待补充
- PASS / FAIL: 待补充
- 日志与视频附件路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage2-smoke/scene-1/`

### 场景 2: 纯保持状态下人为扰动

- 预期现象: 设备可稳定启动并保持最小查询可用, 为后续 Stage 3 人工扰动对比提供可信运行前提
- Stage 2 实测: 待补充
- PASS / FAIL: 待补充
- 日志与视频附件路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage2-smoke/scene-2/`

### 场景 3: 接近目标朝向时的收尾阶段

- 预期现象: 设备可稳定启动并保持最小查询可用, 为后续 Stage 3 收尾表现对比提供可信运行前提
- Stage 2 实测: 待补充
- PASS / FAIL: 待补充
- 日志与视频附件路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage2-smoke/scene-3/`

## 固定动作链

1. 设备发现: `mpy-cli list`
2. 上传规划: `mpy-cli plan`
3. 上传并运行: `mpy-cli deploy --port <master-port>`
4. 最小 smoke: `python3 tools/run_stage2_smoke.py --port <master-port> --source-dir src/master`
5. 最小查询: 记录 `health/tick/vision` 等最小诊断面是否可用
6. 记录 smoke 原始输出、查询原始输出与结论

## 必填观测项

- 设备端口或设备标识
- 本次上传和运行命令
- `mpy-cli plan` 输出中的目标路径与上传计划
- smoke 原始输出
- 最小查询原始输出
- 是否进入主循环, 需要可复核现象
- 最小诊断面是否仍可用
- 失败时的现象、时间点和初步线索

## 执行结果

- 结果: 未执行, 待设备连接后执行
- 结论: 主机侧回归不能替代本页 Stage 2 板端验证
