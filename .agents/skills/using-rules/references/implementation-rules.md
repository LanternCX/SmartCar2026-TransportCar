# 实现阶段规则

## 适用范围

- 本页只承接实现前与实现中的硬规则, 不负责最终收口评审
- 方向与任务目标继续以 `docs/developer/strategy.md`、`docs/developer/tasks.md` 为准
- 若改动触及 PID、运动学、里程计或轨迹行为, 还要联读 `references/strategy-and-control.md`
- 若改动触及硬件事实、视觉协议或联调语义, 还要联读 `references/hardware-and-protocol.md`
- 若改动触及注释补充、注释风格或文档字符串规范, 还要联读 `references/comment-rules.md`

## 基础实现约束

- 目标平台是 RT1021 + MicroPython, 本地开发兼容 Python 3.8+
- 类型提示必须完整, 避免 `Any`, 返回值类型必须显式
- 运行时代码默认不要依赖 `typing`, 如需类型辅助, 优先使用不影响板端导入的兼容写法
- 参数与阈值统一集中到 `config/params.py`
- 禁止静默失败, 只捕获预期异常并保留上下文

## 目录与协作边界

- 目录分层职责必须固定, 各层只承担本层责任
- `services/` 只做编排, 不承载算法、驱动细节或隐藏状态机
- 视觉与独立领域逻辑不得混入服务编排细节
- 依赖方向与跨层调用规则必须统一收口, 禁止下层依赖上层、循环依赖和跨层跳跃调用
- 状态所有权必须唯一, 协作必须显式化
- handler / facade / adapter 只能通过显式上下文接口协作
- 当一个领域模块需要拆成 2 个以上内部实现文件时, 必须优先改为包目录加 `__init__.py`, 不要用共同前缀平铺文件模拟命名空间

## TDD 与验证层选择

- 行为改动必须先选测试层, 并先有失败测试
- 测试驱动开发步骤固定为 RED -> GREEN -> REFACTOR
- 纯逻辑与确定性行为优先放到 `tests/unit/`
- 命令、协议与副作用契约优先放到 `tests/contract/`
- 硬件路径必须进入 `tests/hil/`, 并在可行时补至少一个主机侧回归
- 只有不触及设备路径时, 才能在主机侧验证通过后结束

## 最小执行命令

- 主机侧单元测试: `python3 -m pytest tests/unit -q`
- 主机侧契约测试: `python3 -m pytest tests/contract -q`
- 主机侧联合检查: `python3 -m pytest tests/unit tests/contract -q`
- 设备路径最小 smoke: `python3 tools/run_stage2_smoke.py --port <port>`

## 完成前最小检查

- 必须保留失败测试先于实现的证据
- 目标层级测试必须在本地通过
- 若触及硬件路径, 必须补 `tests/hil/` 留证
- 若进入设备路径, 不得只凭串口有输出就视为完成

## 设备路径判定与阶段要求

- 满足任一条件即进入设备路径: 修改硬件驱动层、修改底盘运行时 owner、依赖真实串口/编码器/IMU/电机/ticker、需要证明板端状态或真实动作链路
- `stage2` 只做最小运行与 smoke 验证, 不验证真实硬件动作
- `stage2` 默认命令顺序固定为 `mpy-cli plan` -> `mpy-cli upload/run/delete` -> smoke 探针
- `stage2` 必验项必须逐项确认: 设备可连接、文件可上传执行、模块可导入、query / smoke 已注册、安全模式入口可见可用
- `stage2` 禁止启动真实动作链路, 也不得因失败直接跳过
- `stage3` 用于人工联调与归因, `uart6` 保持正式链路
- `stage3` 是人工联调阶段, 不是自动 PASS / FAIL 阶段
- `tests/hil/` 中必须留下步骤、预期、实测与 PASS / FAIL 结论
- 联调排查时, 具体硬件事实、视觉协议和失败分类统一回看 `references/hardware-and-protocol.md`

## 实现阶段内存门禁

- 对 `TransportCar`、运行时 owner、诊断 facade、命令装配和板端 probe 的改动, 第一关注点是不要破坏最小内存占用边界
- import-time 副作用必须可见且受限, 禁止目录扫描、自动发现、自动注册和重型单例初始化
- 模块级可变运行时全局属于禁止项
- 可延迟功能若被放回构造期无条件初始化, 视为实现阶段阻断项
- 热路径新增大字符串拼接、大临时容器或无解释动态分配时, 必须先证明必要性
- 低内存下 `?health`、`?tick`、`?vision` 必须保持最小诊断面可用

> 这里的台账与分类只用于实现阶段自检, 不能替代板端实测结果或最终收口评审结论。

> 以下内容是实现阶段自检资产, 用于防止实现过程中越界, 不是最终收口评审结论。

## 实现前内存自检

- 新增了哪些常驻对象
- 它们的唯一 owner 是谁
- 它们属于 A / B / C / D / E 哪一类
- 是否引入了新的重复 owner、重复缓存或隐式共享协议
- 对 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle`、`diag_survival` 有什么影响

## 实现期阻断示例

- 仅凭“文件更小了”就声称内存问题已解决
- 引入新的 facade 或缓存第二份运行时状态
- 为了结构好看增加常驻抽象, 但没有明确必要性
- 在热路径新增大字符串拼接、大临时容器或不可解释的动态分配

## 运行时内存资产台账

- 所有新增运行时对象都必须先回答 4 个问题: 唯一 owner 是谁、在哪个阶段加载、属于哪一类、对 `mem_free` 有什么影响
- 分类规则固定如下:

| 类别 | 含义 | 处理要求 |
| --- | --- | --- |
| `A` | 必需常驻, 系统不上这些对象就不能活 | 允许保留 |
| `B` | 按角色常驻, 只允许在主车或辅车一侧长期存在 | 必须写清角色边界 |
| `C` | 按功能延迟加载, 只有执行到该功能时才允许装配 | 默认延迟 |
| `D` | 调试临时对象 | 默认不得常驻 |
| `E` | 禁止项 | 发现即删除 |

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

## 实现前自检清单

- 新增常驻对象前, 先写清 owner、阶段、分类、触发条件和必要性
- 改动 `TransportCar` 时, 至少要预想并记录以下指标: `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle`、`diag_survival`
- 若板端最小诊断面、延迟加载边界或 owner 唯一性说不清, 先停下补边界, 不要继续扩实现
