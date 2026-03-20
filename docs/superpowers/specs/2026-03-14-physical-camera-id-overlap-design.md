# 物理相机 ID 与重叠类别协议设计文档

## 背景

当前主车双摄方案已经确定采用“单次查询对应单个相机当前帧, 单次响应允许 `0..N` 条检测”的协议方向, 但最近进一步确认了一个关键现实约束:

1. 两颗相机的识别目标集合并不严格互斥。
2. 两颗相机都可能识别 `cargo`、`follower` 或 `obstacle` 中的同一类目标。
3. 因此, 不能再把 `camera_id` 默认理解成“职责相机”或“唯一类别来源”。

如果仍把 `camera_id` 和职责语义绑死, 那么一旦两颗相机都能识别同类目标, 协议命名、主车选择逻辑和 HIL 留证都会发生歧义。

## 目标

1. 明确 `camera_id` 只表示物理相机身份, 不表示逻辑职责。
2. 明确 `category` 只表示检测类别, 可在多颗相机上重复出现。
3. 明确主车必须在车端完成跨相机仲裁, 保持唯一任务状态机所有权不变。
4. 为主控仓库与 `../SmartCar2026-Vision` 视觉仓库提供统一改造基线。

## 非目标

1. 本轮不引入置信度、跟踪 ID 或跨相机目标关联算法。
2. 本轮不要求两颗相机输出统一融合结果, 仍由主车完成最终选择。
3. 本轮不要求一次性解决所有双目几何或时序对齐问题。

## 设计原则

1. `camera_id` 表示物理相机, `category` 表示目标类别, 两者职责不能混淆。
2. 相机端只提供观测, 不决定哪个目标最终驱动车体。
3. 主车仍是唯一任务状态机宿主, 也是唯一跨相机仲裁者。
4. 协议应允许重叠类别, 但不强迫视觉端做复杂融合。
5. 文档、测试和 HIL 留证必须与该语义保持一致, 避免旧“职责相机”口径继续污染实现。

## 总体方案

### 1. `camera_id` 语义

- `camera_id` 只表示物理相机 ID。
- 推荐命名使用物理或安装位姿语义, 例如 `cam_a/cam_b`、`front_cam/side_cam`。
- 不再推荐使用 `cargo`、`obstacle` 这类职责命名作为 `camera_id`。

### 2. `category` 语义

- `category` 表示当前检测框的类别, 例如 `cargo`、`follower`、`obstacle`。
- 同一个 `category` 可以同时出现在多个 `camera_id` 的返回中。
- 协议不要求同一类别只能由一颗相机产生。

### 3. 查询/响应协议

- 主车继续使用 `?frame=<camera_id>` 查询单个物理相机当前缓存帧。
- 被点名相机返回该物理相机当前帧中的 `0..N` 条检测结果。
- 每条检测都携带 `camera_id`、`frame_id`、`category` 和 bbox 字段。
- 最后一条必须是显式 `frame_end=1`。

示例:

```text
?frame=cam_a
camera_id=cam_a,frame_id=12,category=cargo,left=100,top=20,right=140,bottom=90
camera_id=cam_a,frame_id=12,category=follower,left=150,top=25,right=190,bottom=95
camera_id=cam_a,frame_id=12,frame_end=1

?frame=cam_b
camera_id=cam_b,frame_id=33,category=cargo,left=120,top=18,right=170,bottom=110
camera_id=cam_b,frame_id=33,category=obstacle,left=20,top=30,right=80,bottom=140
camera_id=cam_b,frame_id=33,frame_end=1
```

### 4. 主车侧选择层

- 主车不再把某个物理相机硬编码为“cargo 相机”或“obstacle 相机”。
- 主车改为从“多个物理相机当前帧集合”中, 按 `category` 和策略选择本拍状态机输入。
- 推荐优先顺序:
  1. 若已有 `active_target_role`, 先尝试在所有有效帧中继续寻找该角色。
  2. 若没有 active role, 再按策略选择 `follower` / `cargo`。
  3. `obstacle` 先汇总成摘要, 供主车避障逻辑使用, 不直接抢占状态机主目标。

### 5. 物理相机优先级

- 虽然 `camera_id` 不再等于职责, 但主车仍可维护“按物理相机的默认优先级”。
- 例如, 对 `follower/cargo` 可优先信任 `cam_a`, 对障碍摘要可优先信任 `cam_b`。
- 这属于主车配置策略, 不属于协议语义。

### 6. 风险控制

- 若两个相机同时返回同类目标, 主车必须有稳定 tie-break 规则, 否则会发生目标抖动。
- 若继续在文档里把 `camera_id` 写成职责名, 会导致视觉端和车端实现语义错位。
- 若 HIL 留证不改, 现场会继续用 `?frame=obstacle` 这类旧口径查询, 造成误判。

## 影响范围

### 主控仓库

需要同步调整:

1. `docs/Protocol.md`
2. `docs/developer/strategy.md`
3. `tests/hil/2026-03-dual-camera-polling.md`
4. `src/services/transport_car.py`
5. `src/vision/transforms.py`
6. 对应 unit/contract/HIL 测试

### 视觉仓库 `../SmartCar2026-Vision`

需要同步调整:

1. `main.py` 输出格式
2. query/response 处理逻辑
3. 类别与 `camera_id` 透传
4. `README.md` 与 `docs/Protocol.md`
5. 对应 unit/contract 测试

## 验收标准

1. `camera_id` 在主控与视觉仓库中都只表示物理相机身份。
2. 两颗相机都能合法返回同类 `category`。
3. 主车能在重叠类别场景下稳定选择状态机输入, 不发生无规则跳变。
4. 文档、测试、HIL 留证不再使用“职责相机 ID”作为默认前提。
