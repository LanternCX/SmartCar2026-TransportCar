# 2026-03 主车双摄轮询与单状态机 HIL 记录

## 背景

<<<<<<< HEAD
- 任务来源: `docs/superpowers/plans/2026-03-13-dual-camera-single-state-machine.md` Task 6
=======
- 任务来源: `docs/superpowers/plans/2026-03-13-dual-camera-single-state-machine.md` Task 6
>>>>>>> c307ee5 (fix(services): harden boot role and vision runtime)
- 本轮目标: 为主车双摄正交、主车唯一任务状态机、辅车纯执行方案补齐 `stage2 -> stage3 -> HIL` 验证模板
- 当前代码基线: 已完成 Task 1 ~ Task 5 的 host TDD 与 review, Task 6 负责设备侧执行步骤与证据留存

## 主机侧前置验证

### 操作步骤

1. 运行 `python3 -m pytest tests/unit tests/contract -q`

### 预期行为

- unit/contract 全绿
- 说明主车/辅车角色入口、视觉协议、多检测批次、双摄轮询、状态机输入选择层都已通过主机侧回归

### 本轮实际输出

```text
310 passed in 0.32s
```

### 结论

- Host regression: PASS

## 设备信息

- Date: 2026-03-14
- Firmware commit: 未提交工作树
- Port: `/dev/cu.usbmodem101`
- Device: `micropython 1.20.0 | mimxrt | RT1021 MicroPython by NXP & SeekFree with CoreBoard-144Pin V2.1.0`
- Operator: OpenCode

## 车号配置

| 车号 | 角色 | D8 开关 | D9 开关 | 本轮状态 |
| :--- | :--- | :--- | :--- | :--- |
| 1 号车 | 主车 | 关闭(读值=1) | 打开(读值=0) | Stage 2 已验证 |
| 2 号车 | 辅车 | 打开(读值=0) | 关闭(读值=1) | 已换板, Stage 2 已验证 |

说明:

- 当前文档默认采用 `1 号车 = 主车`, `2 号车 = 辅车` 的记录方式
- 若现场实际贴号与此不同, 必须先改表再执行 Stage 3 / HIL
- D8/D9 默认先记录物理开关状态“打开/关闭”, 括号内再补充实际读值 `1/0`; 不要只写电平
- 非法组合 `D8/D9 = 0/0` 或 `1/1` 不属于任何车号配置, 应视为 fail-fast 异常场景

## Stage 2 裸片 smoke

### 操作步骤

1. 执行 `mpy-cli list --reset`
2. 确认可用设备端口
3. 执行 `python3 tools/run_stage2_smoke.py --port <PORT>`

### 预期行为

- 返回 `status=ok`
- query token 完整, `missing=none`
- 最小安全 smoke 可运行
- 临时 probe 自动清理

### 实际输出

#### 2026-03-14 首次执行

```text
status=ok reason=ok
status status=ok reason=ok
queries count=9 missing=none
smoke mode=lite init=0 queries=1 step=0 tick_count=0 snapshots=none
```

#### 2026-03-14 辅车换板后复测

```text
mpy-cli list --reset
发现 1 个可用设备
- /dev/cu.usbmodem101 | micropython 1.20.0 | mimxrt | RT1021 MicroPython by NXP & SeekFree with CoreBoard-144Pin V2.1.0

python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem101
status=ok reason=ok
status status=ok reason=ok
queries count=9 missing=none
smoke mode=lite init=0 queries=1 step=0 tick_count=0 snapshots=none
```

### 结论

- Stage 2: PASS
- 失败归因: none
- 辅车换板后复测: PASS

## Stage 3 `uart3` observe

<<<<<<< HEAD
### 本轮内存治理手动检查补充

操作步骤:

1. 通过 `boot.py` 正常启动主车, 确认不再在 handler 导入阶段直接 OOM
2. 进入正常运行后连续查询 `?health`, `?tick`, `?vision`
3. 记录 `?health` 中 `oom_count` 和 `oom_stage`
4. 视觉链接通后再次查询上述 3 个接口, 对比 `vision_state`, `obs_age_ms`, `oom_count`

预期行为:

- 启动期不再卡在 `services.commanding.handlers` 自动发现
- `?health` 返回包含 `oom_count` / `oom_stage`
- 若状态机停滞但 `tick` 正常增长, 可进一步区分“最近发生过 OOM”还是“条件未满足”

实际结果:

```text
待用户手动记录
```

结论: PENDING

=======
>>>>>>> c307ee5 (fix(services): harden boot role and vision runtime)
### 场景 1: 主车按钮长按入口正确

操作步骤:

1. 按上表将 1 号车设置为主车角色拨码: `D8` 关闭(读值=1), `D9` 打开(读值=0)
2. 长按按钮 1 上电
3. 观察是否进入 `script/pid_identify.py`
4. 重启后长按按钮 2 上电
5. 观察是否进入 `script/calibrate_gyro.py`
6. 再次重启, 不按按钮进入正常运行

预期行为:

- 按钮 1 进入 PID 辨识
- 按钮 2 进入 IMU 校准
- 不按按钮进入 `remote_control.py`

实际结果:

```text
待记录
```

结论: PENDING

### 场景 2: D8 / D9 角色识别正确

操作步骤:

1. 先验证 1 号车配置为 `D8` 关闭(读值=1), `D9` 打开(读值=0)
2. 再验证 2 号车配置为 `D8` 打开(读值=0), `D9` 关闭(读值=1)
3. 最后额外验证非法组合 `0/0` 与 `1/1`
4. 通过 `uart3` 查询 `?health` 或启动日志确认角色

预期行为:

- 1 号车 / 主车 profile 打开视觉轮询与单状态机路径
- 2 号车 / 辅车 profile 不处理视觉, 仅保留执行链路
- 非法组合 fail-fast

实际结果:

```text
待记录
```

结论: PENDING

### 场景 3: 双摄轮询时未被点名相机严格静默

操作步骤:

1. 保持两路视觉共享 `UART6`
2. 主车只发送 `?frame=cam_b`
3. 观察只有 `cam_b` 回包
4. 主车只发送 `?frame=cam_a`
5. 观察只有 `cam_a` 回包

预期行为:

- 未被点名相机严格静默
- 不出现双相机抢答或串帧

实际结果:

```text
待记录
```

结论: PENDING

### 场景 4: 单次查询多条检测响应可稳定收齐

操作步骤:

1. 让 `cam_a` 同帧内同时看到 `cargo` 与 `follower`
2. 主车发送 `?frame=cam_a`
3. 记录多条 `category=...` 消息和最终 `frame_end=1`
4. 通过 `?vision` 或 observe 日志确认主控已收齐本帧

预期行为:

- 一次查询可以收到 `0..N` 条检测
- 最终必须有显式 `frame_end`
- 主控不会在 `frame_end` 前把未结束批次当完整帧
- `camera_id` 仅表示物理相机, `category` 可以重叠

实际结果:

```text
待记录
```

结论: PENDING

### 场景 5: 搬运同时避障时主车仍能稳定驱动辅车

操作步骤:

1. 按上表完成 1 号车 / 2 号车 的角色拨码与上电
2. 让主车搬运视角持续看到 `follower` / `cargo`
3. 让障碍相机同时给出障碍检测
4. 通过 `uart3` 查询 `?vision`、`?lock`、`?motor`、`?pos`
5. 记录 1 号车是否维持唯一状态机推进, 2 号车是否只跟随执行

预期行为:

- 1 号车保持唯一决策
- 2 号车只执行主车下发动作, 不出现独立视觉决策
- 避障观测不会打断主线任务为随机目标

实际结果:

```text
待记录
```

结论: PENDING

## 跨仓库联调准备

### 主控仓库查询约定

- 主车使用 `?frame=cam_a` / `?frame=cam_b` 查询单个物理相机当前缓存帧
- `camera_id` 只表示物理相机身份, 不表示职责相机
- `category` 只表示检测类别, 允许在两颗相机上重叠出现
- 主车负责跨相机仲裁, 视觉端只提供观测

### 视觉仓库期望回包

`cam_a` 示例:

```text
?frame=cam_a
camera_id=cam_a,frame_id=12,category=cargo,left=100,top=20,right=140,bottom=90
camera_id=cam_a,frame_id=12,category=follower,left=150,top=25,right=190,bottom=95
camera_id=cam_a,frame_id=12,frame_end=1
```

`cam_b` 示例:

```text
?frame=cam_b
camera_id=cam_b,frame_id=33,category=cargo,left=120,top=18,right=170,bottom=110
camera_id=cam_b,frame_id=33,category=obstacle,left=20,top=30,right=80,bottom=140
camera_id=cam_b,frame_id=33,frame_end=1
```

### 联调检查清单

1. `cam_a` / `cam_b` 都能响应各自查询
2. 未被点名的相机严格静默
3. 两颗相机都可以返回同类 `category`
4. 每帧最后一条都是 `frame_end=1`
5. 主控 `?vision` 与 `uart3` 日志可观察主车仲裁结果

## HIL 总结

- Host regression: PASS
- Stage 2: PASS
- Stage 3: PENDING
- Final result: PENDING

## 剩余风险

- 若 Stage 2 未执行, 则最小板端 smoke 仍无证据
- 若 Stage 3 未执行, 则无法证明 `uart3` observe、真实双摄静默和主辅协同在板端负载下稳定
- 若现场仍沿用旧职责相机查询口径, 则 HIL 结论会与当前协议语义错位
- 若场景 5 未留证, 则只能说明协议与轮询路径已打通, 不能宣称完整协同搬运闭环已完成
