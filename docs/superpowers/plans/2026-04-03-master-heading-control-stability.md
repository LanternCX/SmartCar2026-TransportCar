# 主车航向控制稳定性实现计划

> **给执行 Agent 的要求:** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。本计划使用 `- [ ]` 复选框跟踪步骤。

**目标:** 在不回退主车主线骨架的前提下，把主车航向控制恢复到更接近 legacy 的稳定语义，让主动转动、自动保持和收尾稳定性重新接近旧版手感。

**架构:** 保留当前 `src/master/motion_runtime.py -> src/master/ctrl/attitude.py -> src/master/state/__init__.py` 的轻量边界，不搬回 legacy 的重型运行时结构。本轮只把 legacy 中真正影响稳定性的 3 件事收回来：主动转动与保持切换语义、按时间累计的航向积分、以及基于当前旋转趋势的抑制项。

**技术栈:** Python, pytest, 当前主车 runtime 主线, legacy 控制参考实现

---

## 提交切片约束

- `docs/superpowers/plans/2026-04-03-master-heading-control-stability.md` 单独作为 plan 提交, 不和代码修改混在一起。
- `docs/superpowers/memory/` 本轮不进入任何提交。
- 代码修改至少拆成两个阶段提交:
  1. 参数与航向控制计算恢复。
  2. 主车运行时接管语义恢复。
- 若实现过程中需要临时调试日志, 调试清理与正式行为修改不要揉成一个提交; 能删掉的调试代码优先在同阶段收干净, 如果必须留痕则单独一段提交并在提交前向用户确认消息。
- 每一次真正执行 `git commit` 前, 先把提交消息发给用户确认, 再执行提交。

### Task 0: 改动前基线留证与 HIL 骨架

**Files:**
- Create: `tests/hil/2026-04-03-master-heading-control-stage2-smoke.md`
- Create: `tests/hil/2026-04-03-master-heading-control-stage3-manual.md`
- Verify: `docs/superpowers/specs/2026-04-03-master-heading-control-stability-design.md`

- [ ] **Step 1: 先写 HIL 留证骨架文件**

两份 HIL 文件都要先写清以下固定字段:

1. 当前工作区状态或基线提交标识
2. legacy 对照版本标识
3. 三个观察场景
4. 预期现象
5. 实测栏位
6. PASS / FAIL 结论栏位
7. 日志与视频附件路径

- [ ] **Step 2: 先记录改动前当前版本基线**

在真正修改代码前, 先记录当前版本的 3 个场景基线:

1. 主动旋转后松手
2. 纯保持状态下人为扰动
3. 接近目标朝向时的收尾阶段

要求:
- 每个场景至少 3 次
- 先留当前版本, 再开始代码实现
- 若拿得到 legacy 对照版本, 同步补 legacy 基线

- [ ] **Step 3: 明确 stage2 / stage3 分工**

在 HIL 文档中明确:

1. `stage2` 只负责设备连接、上传、启动、smoke 和最小查询。
2. `stage3` 只负责人工联调、动作表现对比和手感归因。
3. 两阶段日志、视频和结论分开落到各自文件, 不混写成一页。

- [ ] **Step 4: 检查基线留证是否可复核**

检查项:

1. 改动前当前版本基线已经记录
2. 日志 / 视频路径已经预留
3. 设计文档要求的三个场景都已写入 HIL 骨架

- [ ] **Step 5: 本任务不提交代码, 只确认留证起点**

说明:
- 这一步只建立改动前对照和 HIL 留证骨架
- 不生成 memory 提交
- 不与后续代码提交揉在一起

### Task 1: 锁定主车 legacy 航向语义测试边界

**Files:**
- Modify: `tests/unit/master/test_motion_runtime.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/master/test_runtime_params.py`
- Reference: `src/legacy/control/motion_planner.py`
- Reference: `src/legacy/control/pid_controller.py`

- [ ] **Step 1: 先写失败测试, 明确本轮只改主车语义**

补 3 组主车专属测试, 不再复用“主辅必须同值”的旧断言:

```python
def test_master_heading_correction_matches_legacy_pi_and_yaw_rate_damping() -> None:
    import types

    from master.ctrl.attitude import compute_heading_correction

    state = types.SimpleNamespace(
        heading_hold_enabled=True,
        target_heading_deg=15.0,
        heading_deg=10.0,
        yaw_integral=0.0,
        yaw_kp=0.2,
        yaw_ki=0.1,
        yaw_kd=0.05,
        yaw_i_max=20.0,
        yaw_rate_deg_s=3.0,
        tick_s=0.02,
        auto_omega_max=5.0,
    )

    assert compute_heading_correction(state) == 0.86
```

```python
def test_master_motion_runtime_active_omega_bypasses_heading_hold() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.heading_deg = 27.0
    runtime.target_heading_deg = 12.0
    runtime.heading_target_ready = True
    runtime.yaw_integral = 9.0

    runtime.apply_self_target({"kind": "vel", "vx": 0.0, "vy": 0.0, "omega": 3.0})
    applied = runtime.update_heading_hold(current_heading_deg=27.0)

    assert applied["omega"] == 3.0
    assert runtime.target_heading_deg == 27.0
    assert runtime.yaw_integral == 0.0
```

```python
def test_master_runtime_params_expose_heading_stability_keys() -> None:
    import master.runtime_params as runtime_params

    assert hasattr(runtime_params, "YAW_KD")
    assert hasattr(runtime_params, "HOLD_SPEED_EPS")
```

- [ ] **Step 2: 运行测试确认按预期失败**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_stability_baseline.py tests/unit/master/test_runtime_params.py -q`

Expected:
- 主车航向修正数值断言失败
- 主车主动旋转不再叠加保持的断言失败
- `YAW_KD` / `HOLD_SPEED_EPS` 缺失断言失败

- [ ] **Step 3: 删除或改写不再成立的共享断言**

把 `tests/unit/master/test_stability_baseline.py` 中“主辅 heading correction 必须完全一致”的断言改为“主车必须符合 legacy 语义”, 避免这轮只改主车却继续被辅车约束住。

- [ ] **Step 4: 再跑同一组测试, 确认测试边界正确表达本轮目标**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_stability_baseline.py tests/unit/master/test_runtime_params.py -q`

Expected:
- 仍然失败, 但失败只来自尚未实现的新主车语义

- [ ] **Step 5: 准备测试边界提交**

建议提交消息: `test(control): pin master heading legacy semantics`

执行前动作:
- 先把提交消息发给用户确认
- 确认本次暂不把 plan 和 memory 文件放进代码测试提交

### Task 2: 补齐主车航向稳定参数与状态落点

**Files:**
- Modify: `src/master/runtime_params.py`
- Modify: `src/master/state/__init__.py`
- Modify: `src/master/motion_runtime.py`
- Test: `tests/unit/master/test_runtime_params.py`
- Test: `tests/unit/master/test_structure_runtime.py`

- [ ] **Step 1: 写失败测试, 钉住参数与状态入口**

至少补下面两类断言:

```python
def test_master_motion_runtime_reads_yaw_stability_params() -> None:
    import master.runtime_params as runtime_params
    from master.motion_runtime import MotionRuntime

    old_kd = runtime_params.YAW_KD
    old_eps = runtime_params.HOLD_SPEED_EPS
    runtime_params.YAW_KD = 0.08
    runtime_params.HOLD_SPEED_EPS = 0.25
    try:
        runtime = MotionRuntime()
    finally:
        runtime_params.YAW_KD = old_kd
        runtime_params.HOLD_SPEED_EPS = old_eps

    assert runtime.yaw_kd == 0.08
    assert runtime.hold_speed_eps == 0.25
```

```python
def test_master_runtime_state_exposes_heading_stability_fields() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert hasattr(runtime, "yaw_kd")
    assert hasattr(runtime, "hold_speed_eps")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/master/test_structure_runtime.py tests/unit/master/test_motion_runtime.py -q`

Expected:
- `MotionRuntime` 上缺少 `yaw_kd` / `hold_speed_eps`
- `runtime_params.py` 缺少新的航向稳定入口

- [ ] **Step 3: 最小实现参数与状态接线**

按下面范围改最少代码:

1. 在 `src/master/runtime_params.py` 增加:
   - `YAW_KD = 0.008`
   - `HOLD_SPEED_EPS = 0.01`
2. 在 `src/master/state/__init__.py` 的 `MotionRuntimeState` 中补字段:
   - `self.yaw_kd = 0.0`
   - `self.hold_speed_eps = 0.0`
3. 在 `src/master/motion_runtime.py:create_runtime_state()` 中把新参数装进 runtime state。

- [ ] **Step 4: 回归参数与状态测试**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/master/test_structure_runtime.py tests/unit/master/test_motion_runtime.py -q`

Expected:
- 新参数入口与状态落点测试通过
- 暂未恢复的航向行为测试继续保留为红灯

- [ ] **Step 5: 准备参数与状态提交**

建议提交消息: `refactor(control): wire master heading stability params`

执行前动作:
- 先把提交消息发给用户确认
- `git add` 时排除 `docs/superpowers/memory/**`

### Task 3: 重构主车航向修正计算到 legacy 稳定语义

**Files:**
- Modify: `src/master/ctrl/attitude.py`
- Modify: `src/master/state/__init__.py`
- Test: `tests/unit/master/test_stability_baseline.py`
- Reference: `src/legacy/control/motion_planner.py`
- Reference: `src/legacy/control/pid_controller.py`

- [ ] **Step 1: 写失败测试, 把本轮真正的计算目标钉死**

把测试覆盖到 4 件事:

1. 航向累计按 `tick_s` 累计, 不再每拍直接加角度误差。
2. 航向累计继续受 `yaw_i_max` 限幅。
3. 航向输出要减去 `yaw_kd * yaw_rate_deg_s` 的稳定抑制项。
4. 继续保持最短角差语义。

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py -q`

Expected:
- 新增主车航向计算断言失败
- wrap-around 行为仍通过或仅受主车新公式影响

- [ ] **Step 3: 在 `src/master/ctrl/attitude.py` 写最小实现**

实现要点:

```python
def compute_heading_correction(state, heading_deg=None):
    if not getattr(state, "heading_hold_enabled", True):
        return 0.0
    if heading_deg is None:
        heading_deg = state.heading_deg
    error = _normalize_heading_error(float(state.target_heading_deg) - float(heading_deg))
    dt_s = float(getattr(state, "tick_s", 0.0) or 0.0)
    state.yaw_integral += error * dt_s
    state.yaw_integral = _clamp(state.yaw_integral, -state.yaw_i_max, state.yaw_i_max)
    omega = (error * state.yaw_kp) + (state.yaw_integral * state.yaw_ki)
    omega -= float(getattr(state, "yaw_rate_deg_s", 0.0)) * float(getattr(state, "yaw_kd", 0.0))
    return _clamp(omega, -state.auto_omega_max, state.auto_omega_max)
```

要求:
- 不引入新的大控制器类
- 不把 legacy 的整套 PID 对象层搬回来
- 只在现有主车姿态边界内恢复必要语义

- [ ] **Step 4: 运行主车航向相关测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/master/test_motion_runtime.py -q`

Expected:
- 主车航向修正公式测试通过
- 主动旋转接管相关测试如果仍红, 只剩运行时语义未恢复

- [ ] **Step 5: 准备航向计算提交**

建议提交消息: `refactor(control): restore master heading damping semantics`

执行前动作:
- 先把提交消息发给用户确认
- 确认本次提交只包含 `ctrl/attitude.py`、必要状态补线和对应测试

### Task 4: 恢复主车运行时的主动转动 / 自动保持接管语义

**Files:**
- Modify: `src/master/motion_runtime.py`
- Modify: `src/master/ctrl/attitude.py`
- Test: `tests/unit/master/test_motion_runtime.py`
- Test: `tests/unit/master/test_stability_baseline.py`
- Reference: `src/legacy/control/motion_planner.py:40-68`

- [ ] **Step 1: 写失败测试, 明确运行时切换语义**

新增或补强以下断言:

1. 当 `kind == "vel"` 且 `abs(omega) >= hold_speed_eps` 时:
   - 不叠加自动保持修正
   - 直接输出人工给定的 `omega`
   - 把 `target_heading_deg` 刷新到当前朝向
   - 清空 `yaw_integral`
2. 当 `kind == "vel"` 且 `abs(omega) < hold_speed_eps` 时:
   - 使用保持修正
   - 不在每拍反复刷新目标
3. 当 `kind == "hold"` 时:
   - 继续保持“只有 `vel -> hold` 或目标未就绪时才锁目标”的现有修复

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py -q`

Expected:
- 主动旋转 bypass hold 的断言失败
- 接管保持时机相关断言失败

- [ ] **Step 3: 最小实现运行时切换逻辑**

在 `src/master/motion_runtime.py` 的 `_resolve_applied_target_for_state()` 中按最小改动恢复以下语义:

```python
if kind == "vel":
    vx = float(target.get("vx", 0.0))
    vy = float(target.get("vy", 0.0))
    manual_omega = float(target.get("omega", 0.0))
    if abs(manual_omega) >= float(state.hold_speed_eps):
        capture_heading_target(state)
        return {"kind": "vel", "vx": vx, "vy": vy, "omega": _clamp(manual_omega, -state.auto_omega_max, state.auto_omega_max)}
    return {
        "kind": "vel",
        "vx": vx,
        "vy": vy,
        "omega": compute_heading_correction(state, heading_deg),
    }
```

实现时注意:
- `capture_heading_target(state)` 调用前先保证 `state.heading_deg` 已是当前真实朝向。
- 不把现有 `hold` 目标不重复刷新的修复回退掉。
- 仍沿用当前 `run_base_cycle()` 与 `_apply_motor_output_for_state()` 的轻量骨架。

- [ ] **Step 4: 跑主车控制链回归**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_stability_baseline.py tests/unit/master/test_app.py tests/unit/master/test_structure_runtime.py -q`

Expected:
- 主车运行时接管语义测试通过
- 主车 app / structure 相关回归不被破坏

- [ ] **Step 5: 准备运行时语义提交**

建议提交消息: `refactor(control): restore master heading hold handoff`

执行前动作:
- 先把提交消息发给用户确认
- 若本阶段临时加过调试输出, 在提交前先确认是否删除或单独切片

### Task 5: 留证验证与提交收口

**Files:**
- Verify: `src/master/ctrl/attitude.py`
- Verify: `src/master/motion_runtime.py`
- Verify: `src/master/runtime_params.py`
- Verify: `tests/unit/master/test_motion_runtime.py`
- Verify: `tests/unit/master/test_stability_baseline.py`
- Verify: `docs/superpowers/specs/2026-04-03-master-heading-control-stability-design.md`
- Modify: `tests/hil/2026-04-03-master-heading-control-stage2-smoke.md`
- Modify: `tests/hil/2026-04-03-master-heading-control-stage3-manual.md`

- [ ] **Step 1: 运行主机侧完整回归**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_stability_baseline.py tests/unit/master/test_runtime_params.py tests/unit/master/test_structure_runtime.py tests/unit/master/test_app.py tests/unit/master/test_runtime_loop.py -q`

Expected:
- 本轮直接相关主机侧测试全部通过

- [ ] **Step 2: 做板端对比留证**

按设计文档要求至少完成以下场景, 每个场景 3 次:

1. 主动旋转后松手, 观察主车是否能接住当前朝向。
2. 纯保持状态下人为扰动, 观察主车是否比当前版本更快回正。
3. 接近目标朝向时, 观察是否比当前版本更少拖尾或摆动。

留证要求:
- 至少保留串口日志或控制链日志
- 优先补一段实机视频
- 同时对照当前版本与 legacy 稳定基线

并把结果分别写入:

1. `tests/hil/2026-04-03-master-heading-control-stage2-smoke.md`
   - 记录设备连接、上传、运行、smoke、最小查询和 stage2 结论
2. `tests/hil/2026-04-03-master-heading-control-stage3-manual.md`
   - 记录人工联调步骤、三类场景对比、日志路径、视频路径和 stage3 结论

- [ ] **Step 3: 整理提交队列, 明确哪些文件本轮不提交**

本轮提交前再次检查:

```bash
git status --short
```

确认:
- `docs/superpowers/memory/**` 不进入本轮提交
- plan 提交与代码提交分开
- 临时调试垃圾不进入正式提交

- [ ] **Step 4: 准备最终收口提交消息并向用户确认**

若前面已按阶段提交, 这里仅确认是否还需要补一个验证或清理提交。

候选消息示例:
- `test(control): pin master heading legacy semantics`
- `refactor(control): wire master heading stability params`
- `refactor(control): restore master heading damping semantics`
- `refactor(control): restore master heading hold handoff`

- [ ] **Step 5: 完成后请求代码评审并再决定是否记录 memory**

只有当以下条件全部满足时, 才进入后续 memory 记录决策:

1. 主机侧回归通过
2. 板端留证完成
3. 用户确认本轮稳定性方向正确
4. 本轮计划提交与代码提交已经按切片收口
