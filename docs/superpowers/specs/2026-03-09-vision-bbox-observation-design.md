# 视觉识别框观测设计文档

## 背景

当前车端视觉协议只接收 `x,y` 两个像素坐标，并在状态机中直接把它们当成横向和纵向对正依据。这个模型只能表达“单点”，无法表达识别框的完整几何信息。

对当前搬运流程来说，这会带来两个问题：

1. 纵向对正的真实依据是“目标框底边”和“画面底边”的关系，而不是某个孤立点的 `y`
2. 当状态机需要判断目标是否稳定、是否可以跳转、是否需要回退时，缺少完整框信息会让判据不完整，难以解释和调试

## 目标

1. 将视觉观测从 `x,y` 升级为完整识别框 `left,top,right,bottom`
2. 让车端基于识别框派生出 `center_x`、`center_y`、`bottom`、`width`、`height`
3. 将横向对正统一建立在框中心横坐标上
4. 将纵向对正统一建立在框底边与画面底边的关系上
5. 让 `?vision` 能回传完整观测框和关键派生信息，便于调试状态与跳转

## 非目标

- 不在本次改动中引入类别、置信度、角度等额外视觉字段
- 不在本次改动中重构 OpenArt 侧目标选择策略
- 不改动现有推行、返回阶段的总体动作流程

## 设计决策

### 1. 视觉协议切换为完整框

- `UART6` 上的合法视觉帧改为恰好包含 `left,top,right,bottom` 四个键
- 车端不再将 `x,y` 视为可驱动视觉状态机的完整观测
- 视觉协议层负责把完整框转换为结构化 `VisionObservation`

### 2. 观测模型保留完整框并提供派生量

- `VisionObservation` 保存 `left`、`top`、`right`、`bottom`
- 同时提供以下派生属性：
  - `center_x`
  - `center_y`
  - `width`
  - `height`

这样状态机和诊断层都不需要重复手写框几何计算。

### 3. 状态机判据改为“中心 + 底边”

- `ALIGN_ANGLE`：使用 `center_x` 对齐横向误差
- `ALIGN_DIST`：使用 `bottom` 对齐纵向误差
- `ALIGN_DX`：继续使用 `center_x` 做最终横向确认，但回退到距离阶段时改看 `bottom`
- `PUSHING`：保留小幅横向纠偏，纠偏输入改为 `center_x`

### 4. 目标参数语义显式化

- 将配置中的纵向视觉目标从“目标点 y”改为“目标底边 bottom”
- 默认目标底边使用画面底边语义，配置名改为 `VISION_TARGET_BOTTOM_PX`

### 5. 诊断快照补全完整观测框

`?vision` 快照至少补充：

- `obs_left`
- `obs_top`
- `obs_right`
- `obs_bottom`
- `obs_center_x`
- `obs_center_y`

保留 `target_x`、`target_y`、`target_angle`，便于继续观测状态机输出到控制层的绝对目标。

## 风险与缓解

1. 风险：旧 OpenArt 若仍继续发送 `x,y`，将无法再提供完整视觉状态输入
   - 缓解：协议层将其视为不完整视觉载荷，不再让它进入视觉状态机
2. 风险：完整框切换后，原有测试和诊断字段会大面积回归
   - 缓解：先补 unit / contract 测试，再改实现与文档
3. 风险：状态机虽然只改像素判据，但仍集成在 `TransportCar`
   - 缓解：至少完成主机侧 unit / contract 回归；板端 Stage 2 / Stage 3 / HIL 另行留证

## 验收标准

- `VisionProtocol` 能解析 `left,top,right,bottom` 并生成完整观测对象
- `VisionStateMachine` 的横向判据基于框中心，纵向判据基于框底边
- `TransportCar` 的 `?vision` 快照能返回完整框字段与派生字段
- 相关 `tests/unit` 与 `tests/contract` 通过
