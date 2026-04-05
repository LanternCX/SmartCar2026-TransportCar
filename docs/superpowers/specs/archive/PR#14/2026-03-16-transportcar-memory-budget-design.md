# 搬运车最小内存占用重构设计

## 背景

当前 `src/services/transport_car.py` 已经成为典型的 God object。板端探针已证明, 在干净模块清理后, `from services.transport_car import TransportCar` 仍可能因申请约 `4168 bytes` 而 OOM。与此同时, 运行时错误路径会继续出现 `ERRRAW memory allocation failed, allocating 1280 bytes / 1148 bytes`, 说明问题不再只是单点日志放大器, 而是导入期常驻依赖、初始化期装配策略、运行时 owner 边界和低内存退化策略共同失衡。

本设计不把“文件更小”当作目标本身, 而把“满足最小内存占用指标”作为唯一硬门禁。文件拆分、结构清晰和 review 可读性都属于结果, 不是验收主指标。

## 目标

- 让功能在执行时只加载最小依赖, 降低 import-time 和 init-time 内存峰值
- 建立面向 RT1021 + MicroPython 的内存资产台账, 明确必要常驻和可延迟对象
- 将 `TransportCar` 降级为编排器, 把控制、视觉、命令、诊断按 owner 拆分
- 把“节省内存”写入项目代码规范和 code review 门禁, 长期防止架构回弹
- 保证低内存时 `?health/?tick/?vision` 等最小诊断面优先存活

## 非目标

- 不以“先恢复所有现有行为”作为单独目标; 行为一致性要和内存门禁一起验证
- 不为未来假设需求引入插件化、事件总线或复杂动态装配框架
- 不把单文件行数下降误认为完成标准; 若内存指标没有改善, 则拆分无效

## 设计原则

- import-time 只定义代码, 不做重装配, 不做自动发现, 不做批量注册
- 每个运行时状态只允许一个 owner, facade 和 handler 只能只读访问
- 常驻内存优先级高于结构美观; 任何结构调整都要对板端内存指标负责
- query 优先于日志; 低内存时日志必须 best-effort, 最小诊断必须保活
- 主车 / 辅车按角色加载依赖, 禁止相同全量装配
- 文件拆分必须与依赖切断一起发生, 禁止“拆文件不拆常驻内存”

## 内存资产模型

### A 类: 必需常驻

系统不上这些对象就不能活, 必须在最小启动路径中存在:

- `uart3` / `uart6`
- 时间基准与 ticker flag
- 最小错误 / OOM 计数
- 角色信息
- safe stop 能力
- 最小 query 入口

### B 类: 按角色常驻

仅在主车或辅车某一侧长期存在:

- 主车视觉最小运行时
- 角色相关目标选择或配置缓存

### C 类: 按功能延迟加载

只有执行到该功能时才允许装配:

- 完整底盘控制链
- 完整视觉状态机推进
- 完整 command / query handlers
- 扩展 diagnostics 和调试命令

### D 类: 调试临时对象

只能在 observe / trace / probe 时存在, 默认不得常驻:

- `stage2/stage3` 追踪探针
- 扩展 trace 文本
- 额外日志 sink

### E 类: 禁止项

- 模块级可变运行时全局
- import-time 自动发现 / 自动注册
- 重复 owner 或重复缓存同一状态
- 热路径反复创建大 `dict/list/str`
- 为了 review 好看而引入的多层空抽象

## Review 主指标

所有重构和后续 PR 都必须围绕以下指标评审:

- `mem_free_after_import`
- `mem_free_after_core_init`
- `mem_free_after_feature_init`
- `mem_free_runtime_idle`
- `diag_survival`: 低内存时 `?health/?tick/?vision` 是否仍可用

Review 结论必须回答这 5 个问题:

1. 新增了哪些常驻对象?
2. 它们为什么属于 A / B 类, 而不是 C / D 类?
3. 是否引入了新的重复 owner 或全局状态?
4. 板端 `mem_free` 指标有无变差?
5. 最小诊断面是否仍存活?

## Review 阻断条件

命中任一项, review 直接不通过:

- 新增 import-time 自动发现或自动注册
- 新增模块级可变运行时状态
- 可延迟功能被放进构造期无条件初始化
- 热路径新增明显动态分配且无必要性证明
- 没有提供板端内存证据或探针结果
- 结构更清晰, 但常驻内存 / 导入峰值没有下降

## 目标架构

### `TransportCar`

降级为生命周期编排器 / facade, 只负责:

- 组装 owner
- 控制装配顺序
- 暴露统一外观接口
- stop / reset 时统一释放资源

目标代码量: `<= 300` 行, 理想目标 `150-250` 行

### `RuntimeCore`

负责最小生存能力:

- `uart3` / `uart6`
- ticker flag / 时间接口
- `oom_count` / `last_oom_stage` / `last_exception_text`
- safe stop
- 角色 profile

### `MinimalCommandRuntime`

负责最小 query 路由和上下文, 不加载完整 handler 集。低内存时系统至少应靠它回答 `?health/?tick/?vision`。

### `MinimalDiagnostics`

只读其他 owner 的公开快照接口。diagnostics 自身不得复制运行时状态, 也不得成为新的状态 owner。

### `MotionRuntime`

持有 `imu`、电机、编码器、姿态估计、PID、底盘控制器等完整控制链。只有真正启动控制功能时才装配。

### `VisionRuntimeService`

主车专属。最小协议缓存和完整状态机推进分层装配; 辅车不允许装入完整视觉依赖。

### `FullCommandRuntime`

完整 command / query handlers、扩展调试命令和高级路由装配。禁止在 import-time 全量注册。

## 状态 owner 规则

- `chassis_state` 只能归 `MotionRuntime`
- 视觉观测、frame slot、状态机状态只能归 `VisionRuntimeService`
- router / handler registry 只能归 `CommandRuntime`
- diagnostics 只能只读聚合, 不得缓存第二份运行时状态
- `script.remote_control.py` 中的 `car` / `pit1` 只是脚本句柄, 不再承担跨模块共享状态职责

## 规范与 code review 更新

以下要求必须进入项目规范, 并同步到 code review 清单:

- import-time 禁止目录扫描、自动发现、自动注册、重型单例初始化
- init-time 只能拉起 A 类和必要 B 类对象
- 所有 C / D 类对象必须写清加载触发条件
- 禁止模块级可变全局状态和隐式共享协议
- 热路径不得引入无界字符串拼接和大临时容器
- 任何结构优化若不能降低内存指标, 则不算有效重构
- review 输出必须包含:
  - 常驻内存变化
  - 新增 owner
  - 延迟加载变化
  - 板端内存证据
  - 是否满足最小内存占用指标

## 迁移顺序

1. 建立内存资产台账和板端测量探针
2. 抽出 `RuntimeCore`, 保持行为入口不变
3. 抽出 `MinimalDiagnostics` 和 `MinimalCommandRuntime`, 先保住最小可观测性
4. 再拆 `MotionRuntime`、`VisionRuntimeService`、`FullCommandRuntime`
5. 最后清理残余全局变量、重复 owner 和隐式共享协议

## 验收标准

- `import services.transport_car` 的内存峰值显著下降
- `TransportCar` 构造不再默认拉起全部功能依赖
- 主车 / 辅车按角色装配最小依赖
- `?health/?tick/?vision` 在低内存时优先存活
- `src/services/transport_car.py` 从 God object 降为薄编排层
- 代码规范与 code review 明确以“最小内存占用指标”为首要门禁
