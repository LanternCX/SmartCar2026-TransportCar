# 2026-04-03 主车航向控制稳定性 Stage 3 人工联调留证

## 状态

- 当前状态: 未执行, 待设备连接后执行
- 当前基线提交: `c95f10c`
- 当前工作区状态: 存在未提交的 `docs/superpowers/memory/**` 与 `.agents/skills/using-rules/references/implementation-rules.md` 改动, 不属于本次主车控制实现提交
- legacy 对照版本标识: 待补充具体提交号, 当前参考 `src/legacy/control/motion_planner.py` 与 `src/legacy/control/pid_controller.py`
- 留证路径: `tests/hil/2026-04-03-master-heading-control-stage3-manual.md`
- 附件预留路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage3-manual/`
- 执行限制: 本页只记录人工联调、动作表现对比与手感归因, 不代替 Stage 2 启动和 smoke 结果

## Stage 3 分工

- 只负责人工联调、动作表现观察和当前版本与 legacy 的对比
- 三个场景的日志、视频和结论只写在本页, 不混写到 Stage 2
- 不把单次主观感受直接写成完成结论, 必须有重复记录和附件路径

## 当前版本改动前基线

- 基线状态: 未执行, 待设备联调后补齐
- 要求: 先记录当前版本基线, 再记录后续实现版本结果
- 重复次数要求: 每个场景至少 3 次
- legacy 对照要求: 如果能取得 legacy 稳定版本, 同步补 legacy 基线

## 观察场景

### 场景 1: 主动旋转后松手

- 预期现象: 松手后应能接住当前朝向, 不应继续明显残留转动
- 当前版本基线实测: 待补充
- 后续实现版本实测: 待补充
- legacy 对照实测: 待补充
- PASS / FAIL: 待补充
- 日志与视频附件路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage3-manual/scene-1/`

### 场景 2: 纯保持状态下人为扰动

- 预期现象: 受扰后应更干脆地回正, 不应出现明显争抢或持续偏软
- 当前版本基线实测: 待补充
- 后续实现版本实测: 待补充
- legacy 对照实测: 待补充
- PASS / FAIL: 待补充
- 日志与视频附件路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage3-manual/scene-2/`

### 场景 3: 接近目标朝向时的收尾阶段

- 预期现象: 接近目标后应更利索收住, 不应明显拖尾或摆动
- 当前版本基线实测: 待补充
- 后续实现版本实测: 待补充
- legacy 对照实测: 待补充
- PASS / FAIL: 待补充
- 日志与视频附件路径: `tests/hil/artifacts/2026-04-03-master-heading-control-stage3-manual/scene-3/`

## 记录要求

- 每个场景至少 3 次
- 记录版本标识、参数、执行人、时间
- 记录串口日志路径与视频路径
- 结论必须明确区分当前版本、后续实现版本与 legacy 对照版本

## 执行结果

- 结果: 未执行, 待设备连接后执行
- 结论: 当前仅建立留证骨架, 不记录伪结果
