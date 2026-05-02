# 主车视觉端 P 环搜索控制设计

> 执行状态: Archive
> 关联计划: `docs/superpowers/plans/archive/PR#64/2026-05-01-master-vision-p-control-search-plan.md`
> 适用范围: 主车 RT1021 搜索状态、主车 OpenART Vision master、主车本地 `UART6` 视觉链路

## 1. 目标

本轮目标是让主车搜索红色沙包时采用与辅车跟随一致的职责分工: OpenART Vision master 在视觉端完成目标误差到速度控制量的 P 环计算, 并通过 `v,<vx>,<vy>` 下发给主车 RT1021。主车 RT1021 只维护搜索上下文、可靠事件确认、状态切换和速度输入优先级, 不根据视觉观测字段计算 P 控制量。

搜索阶段仍以“找到目标”为边界。目标进入画面目标窗口并连续稳定后, OpenART Vision master 通过可靠 `TARGET_FOUND` 事件通知主车 RT1021, 主车进入 `OBJECT_FOUND` 并输出零平移速度。

## 2. 改动面评估

本轮改动跨两个仓库, 改动面较大:

- 视觉仓库 `../SmartCar2026-Vision/master/main.py` 的主车搜索输出语义从观测数据流转为速度控制数据流。
- 车端仓库 `src/vision/master/forward_runtime.py` 需要消费本车 `UART6` 上的 `v` 速度包。
- 车端主车搜索状态机保留状态和事件职责, 固定搜索速度不作为车端主搜索控制来源。
- `docs/developer/protocol.md`、`docs/developer/vision.md`、`docs/developer/control.md`、`docs/developer/state.md` 需要同步当前协议和职责事实。
- 两个仓库的主机侧行为测试和契约测试需要同步更新。

因此本轮需要独立 Spec 和 Plan, 并按 Subagent-Driven Development 拆任务执行。

## 3. 方案取舍

### 方案 A: 车端根据 `o` 观测包做 P 环

OpenART Vision master 继续发送 `o,<context_id>,<x>,<y>,<value>`, 主车 RT1021 在角色层计算 P 控制量。

该方案让车端承担视觉误差控制, 与辅车“视觉端输出速度修正量”的职责分工不一致, 也会让主车角色层同时维护状态机、通信和视觉 P 控制。

### 方案 B: OpenART Vision master 输出最终搜索速度

OpenART Vision master 在建立 hook 上下文后, 每帧输出 `v,<vx>,<vy>`。有目标时, `vx / vy` 来自识别框中心点误差的 P 环; 无目标时, 输出视觉端配置的搜索速度。主车 RT1021 在 `SEARCH_OBJECT` 中直接使用该速度包作为本车搜索速度输入。

该方案最接近辅车视觉链路: 视觉端负责识别、误差计算和 P 环速度生成, 车端负责速度入口编排与底盘执行。

### 方案 C: 车端固定搜索速度 + 视觉端 P 修正速度

主车 RT1021 继续输出固定搜索速度, OpenART Vision master 输出视觉修正量, 车端把两者相加。

该方案接近辅车“前馈 + 修正”的融合方式, 但搜索目标居中时仍会叠加固定搜索速度, 不利于稳定触发 `TARGET_FOUND`。同时车端仍需要维护搜索速度控制策略。

### 选定方案

本设计采用方案 B。主车视觉端输出最终搜索速度, 车端不计算主车搜索 P 环, 也不依赖 `o` 观测包推进控制。

## 4. 职责边界

### OpenART Vision master

- 接收主车 RT1021 下发的 `s,<reliable_seq>,<context_id>,<state>,<target>,<arg>`。
- 使用 `a,<reliable_seq>` 确认搜索上下文。
- 在已建立搜索上下文时识别红色沙包候选目标。
- 基于识别框中心点 `x / y` 计算视觉 P 环速度。
- 通过 `v,<vx>,<vy>` 下发主车搜索速度控制量。
- 基于同一套误差、面积和稳定帧条件创建 `TARGET_FOUND` 事件。
- 通过 `r,<reliable_seq>,<context_id>,<event>,<value>` 可靠回报目标找到事件。
- 不维护全局状态机, 不输出 `omega`。

### 主车 RT1021

- 维护 `IDLE -> SEARCH_OBJECT -> OBJECT_FOUND` 搜索状态。
- 进入 `SEARCH_OBJECT` 时建立视觉 hook 上下文。
- 处理主车 `UART6` 上的 `v`、`a`、`r` 包。
- 在 `SEARCH_OBJECT` 中使用主车视觉 `v` 包作为本车搜索速度输入。
- 收到匹配上下文的 `TARGET_FOUND` 后进入 `OBJECT_FOUND`。
- 在 `OBJECT_FOUND` 中输出零平移速度。
- 保持 `UART3` 上游速度输入优先级: 同一控制拍存在合法 `UART3` 速度包时, 以 `UART3` 输入为最终底盘速度。
- 不根据 `o` 观测包计算主车搜索 P 环。

## 5. 协议设计

### 主车本地视觉链路

主车本地 `UART6` 同时承载:

- RT1021 -> OpenART: `s` 状态 / hook 上下文同步包。
- OpenART -> RT1021: `a` 同步确认包。
- OpenART -> RT1021: `v` 主车搜索速度数据流包。
- OpenART -> RT1021: `r` 可靠事件回报包。
- RT1021 -> OpenART: `a` 事件确认包。

`v` 包格式沿用现有速度短包:

```text
v,<vx>,<vy>
```

字段语义:

| 字段 | 含义 |
| --- | --- |
| `vx` | OpenART Vision master 生成的主车搜索态车体系 x 方向速度 |
| `vy` | OpenART Vision master 生成的主车搜索态车体系 y 方向速度 |

主车视觉 `v` 包不携带 `omega`。主车方向保持仍由底盘本地能力承担。

### `o` 观测包边界

主车搜索控制不依赖 `o` 观测包。OpenART Vision master 默认不需要周期发送 `o` 包。若后续需要诊断观测数据, 应作为单独诊断能力设计, 不把 `o` 重新放回主车搜索控制主线。

### 可靠包边界

`s/a/r` 可靠包语义保持不变:

- `s` 建立搜索上下文。
- `a` 确认可靠包。
- `r` 回报 `TARGET_FOUND`。
- `reliable_seq` 只用于可靠包确认、重发和去重。
- `context_id` 只用于业务上下文匹配。

## 6. 视觉 P 环设计

### 目标点

主车视觉搜索目标点采用画面中线和画面下三分之二点:

- `target_x = image_width / 2`
- `target_y = image_height * 2 / 3`

### 误差来源

有目标时, 控制误差直接来自识别框中心点:

- `err_x = bbox_center_x - target_x`
- `err_y = bbox_center_y - target_y`

识别框中心点来自 `blob.rect()` 或 OpenART blob 的中心字段。主车搜索 P 环不使用最小外接旋转矩形, 不使用角点边长, 不使用 `marker_span`。

### 控制量

视觉端按轴计算速度控制量:

- 横向误差在死区内时, `vx = 0`。
- 横向误差超出死区时, `vx = err_x * MASTER_CONTROL_KP_X`。
- 纵向误差在死区内时, `vy = 0`。
- 纵向误差超出死区时, `vy = err_y * MASTER_CONTROL_KP_Y`。
- `vx / vy` 分别按配置上限限幅。

P 环增益、死区、速度上限和无目标搜索速度都维护在视觉仓库 `master/main.py` 的主车配置区。增益正负号作为调参项显式保留, 板端联调按相机安装和车体系方向确认。

### 无目标输出

无有效红色目标时, OpenART Vision master 输出配置的搜索速度:

```text
v,<MASTER_MISSING_SEARCH_VX>,<MASTER_MISSING_SEARCH_VY>
```

这保证主车接入视觉后能够主动搜索, 同时仍把搜索速度控制来源放在视觉端。

### 找到目标

当红色目标满足以下条件时, OpenART Vision master 创建 `TARGET_FOUND` 事件:

- 候选目标面积达到阈值。
- `err_x` 进入横向容差。
- `err_y` 进入纵向容差。
- 条件连续满足指定帧数。

事件创建后, OpenART Vision master 按可靠通信节奏重复发送同一个 `r` 包, 直到收到主车 RT1021 的匹配确认。

## 7. 车端速度优先级

主车角色层在单拍内使用以下优先级:

1. 合法 `UART3` 速度包: 写入本车底盘并转发 `UART8`。
2. `OBJECT_FOUND`: 写入零平移速度。
3. `SEARCH_OBJECT` 且存在主车视觉速度: 写入最近主车视觉 `v` 包。
4. `SEARCH_OBJECT` 且尚无主车视觉速度: 写入零平移速度, 并继续发送或等待视觉上下文确认。
5. `IDLE`: 不写入搜索速度。

主车视觉 `v` 包只服务本车搜索, 不转发到 `UART8`。辅车仍只接收来自 `UART8` 的主辅前馈和本车 `UART6` 的辅车视觉速度修正。

## 8. 测试策略

### 视觉仓库

需要覆盖:

- 主车视觉能格式化 `v,<vx>,<vy>`。
- 无目标时输出配置的搜索速度。
- 有目标时使用识别框中心点 `x / y` 生成 P 控制量。
- 横向和纵向死区会输出零量。
- `vx / vy` 受配置上限限制。
- 找到事件使用同一套识别框中心误差判断稳定窗口。
- 主车搜索路径不依赖最小外接旋转矩形或 `marker_span`。
- `s/a/r` 可靠通信语义保持。

### 车端仓库

需要覆盖:

- 主车 `UART6` 收到 `v` 包后在 `SEARCH_OBJECT` 中写入本车底盘。
- 主车视觉 `v` 包不转发到 `UART8`。
- `UART3` 速度包优先级高于主车视觉 `v` 包。
- `OBJECT_FOUND` 状态忽略主车视觉 `v` 包并输出零平移速度。
- 匹配 `TARGET_FOUND` 事件仍会确认并触发状态迁移。
- 非匹配事件仍会确认但不触发状态迁移。
- 主车状态机不计算视觉 P 控制量。

## 9. 文档同步范围

- `docs/developer/protocol.md`: 登记主车 `UART6` 上的 `v` 搜索速度语义, 收口 `o` 的主车搜索控制边界。
- `docs/developer/vision.md`: 说明 OpenART Vision master 的 P 环职责和识别框中心点误差来源。
- `docs/developer/control.md`: 说明 `SEARCH_OBJECT` 的速度来源改为主车视觉 `v` 包。
- `docs/developer/state.md`: 说明状态机只维护状态、上下文和事件, 不计算视觉 P 环。
- `../SmartCar2026-Vision/README.md`: 说明 master 入口输出 `v` 搜索速度、保留 `s/a/r` 可靠事件链路。

## 10. 验收标准

- 主车 OpenART 接收搜索上下文后, 能持续输出 `v,<vx>,<vy>`。
- 主车 OpenART 的 `vx / vy` 有目标时只依赖识别框中心点 `x / y` 误差, 不依赖最小外接旋转矩形边长。
- 主车 RT1021 在 `SEARCH_OBJECT` 中消费主车视觉 `v` 包并驱动本车底盘。
- 主车 RT1021 不用 `o` 观测包计算主车搜索 P 环。
- 主车 RT1021 收到匹配 `TARGET_FOUND` 后进入 `OBJECT_FOUND` 并输出零平移速度。
- `UART3` 遥控输入仍保持最高优先级。
- 主车视觉 `v` 包不转发给辅车。
- 车端和视觉仓库主机侧测试通过。
- 板端联调记录包含串口观测、速度方向、目标进入窗口、事件确认和停车结果。
