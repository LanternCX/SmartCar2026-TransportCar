# 搬运车运行时内存资产台账

## 目的

本台账用于约束 `TransportCar` 相关重构和后续 code review。首要目标不是让结构更整齐, 而是保证板端最小内存占用指标达标。

所有新增运行时对象都必须先回答 4 个问题:

1. 它的唯一 owner 是谁?
2. 它在哪个阶段加载?
3. 它属于必需常驻, 按角色常驻, 还是可延迟加载?
4. 它对板端 `mem_free` 有什么影响?

## 分类规则

- `A`: 必需常驻, 系统不上这些对象就不能活
- `B`: 按角色常驻, 只允许在主车或辅车一侧长期存在
- `C`: 按功能延迟加载, 只有执行到该功能时才允许装配
- `D`: 调试临时对象, 默认不得常驻
- `E`: 禁止项, 发现即视为 review 阻断

## 台账字段

| Asset | Owner | Phase | Class | Trigger | Duplicate | Action | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `uart3` | `RuntimeCore` | `core_init` | `A` | boot | no | keep | `stage2 probe` | 最小日志和 query 回包通道 |
| `uart6` | `RuntimeCore` | `core_init` | `A` | boot | no | keep | `stage2 probe` | 命令和视觉输入通道 |
| `oom_count` / `last_oom_stage` | `RuntimeCore` | `core_init` | `A` | boot | no | keep | `?health` | 低内存时必须可读 |
| `last_exception_text` | `RuntimeCore` | `core_init` | `A` | boot | no | keep | `?health` | 仅保留最小错误上下文 |
| 角色 profile | `RuntimeCore` | `core_init` | `A` | boot | no | keep | boot role | 决定主车 / 辅车装配边界 |
| 最小 query 路由 | `MinimalCommandRuntime` | `core_init` | `A` | boot | no | keep | `stage2 lite` | 仅保活 `health/tick/vision` |
| 完整 handlers 装配 | `FullCommandRuntime` | `feature_init` | `C` | first command feature | yes | delay | board trace | 禁止 import-time 全量注册 |
| `vision_runtime` | `VisionRuntimeService` | `feature_init` | `B` | main role only | yes | split/delay | `stage2 full` | 主车允许, 辅车禁止 |
| 视觉状态机推进 | `VisionRuntimeService` | `runtime` | `C` | vision active | yes | delay | stage3 observe | 不是最小启动必需 |
| `chassis_state` | `MotionRuntime` | `feature_init` | `C` | motion activated | yes | move owner | board trace | 禁止同时挂在多个 facade |
| IMU / 电机 / 编码器 | `MotionRuntime` | `feature_init` | `C` | motion activated | no | delay | board trace | 不应在最小 query 路径常驻 |
| logger manager | `RuntimeCore` | `core_init` | `A` | boot | no | slim | `?log` / board log | 只保留低分配快路径 |
| 扩展 diagnostics | `MinimalDiagnostics` 之外的 owner | `feature_init` | `C` | debug feature | yes | delay | stage3 observe | query 优先于 debug 文本 |
| `stage2_full_trace_probe` | tools probe | `diag` | `D` | manual observe | no | temp only | manual run | 默认不参与运行态 |
| 模块级可变运行时全局 | none | `import` | `E` | never | n/a | delete | review block | 包括隐式单例和共享缓存 |
| import-time 自动发现 / 自动注册 | none | `import` | `E` | never | n/a | delete | review block | 直接抬高导入峰值 |

## Review 必答项

每次 `TransportCar` 相关 review 必须明确写出:

- 本次新增了哪些内存资产
- 它们的 owner 是谁
- 它们属于 `A/B/C/D/E` 哪一类
- 是否引入了新的重复 owner 或全局状态
- 对以下指标的影响:
  - `mem_free_after_import`
  - `mem_free_after_core_init`
  - `mem_free_after_feature_init`
  - `mem_free_runtime_idle`
  - `diag_survival`

## Review 阻断条件

命中以下任一项, 直接判定为不通过:

- 新增 import-time 自动发现, 自动注册或批量装配
- 新增模块级可变运行时状态
- 可延迟功能被放入构造期无条件初始化
- 热路径新增明显动态分配且没有必要性证明
- 结构更清晰, 但板端 `mem_free` 指标无改善或变差
- 没有提供板端证据, 探针结果或明确的 `hil_pending` 标记
