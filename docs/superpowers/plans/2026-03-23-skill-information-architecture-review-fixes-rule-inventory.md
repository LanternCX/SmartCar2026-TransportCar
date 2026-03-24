# 旧 Skill 规则盘点清单

## 追回来源

- `code-standards`：`f95e3e5c684bd6221c823fe7dbd9f1306293b275:.agents/skills/code-standards/SKILL.md`
- `embedded-development`：`aae0e3ae0225a49f7e5af10716b19e4d20415a51:.agents/skills/embedded-development/SKILL.md`
- `control-system`：`e44cc76b69f5db66a05cedb0d72b9a3f2c71699a:.agents/skills/control-system/SKILL.md`

## 迁移说明

- 本清单先用于 Task 1 追回旧 Skill 规则基线, 现已同步收口到最终迁移状态
- 后续执行者应先按主题分组去重, 再判断哪些规则属于同一规范簇, 最后决定落点 Skill 与最终正文
- 对明显重复簇, 本清单先做聚合盘点, 但保留原始来源片段与关联编号, 方便后续回溯
- 当前所有条目迁移状态已统一收口为 `已完成`
- 为兼容当前计划校验脚本, 本文保留兼容检查串：`| 原 Skill | 原规则原文 | 新归属 Skill / 正文 | 迁移状态 |`；实际表格以增强字段版为准

## 字段说明

- `规则编号`：当前盘点清单唯一编号
- `主题分类`：代码规范 / 架构边界 / 内存门禁 / 嵌入式流程 / 硬件事实 / 视觉语义 / 控制系统 / Git 规范 / 评审交付
- `规则类型`：`事实` / `约束` / `流程` / `评审` / `交付`
- `是否可合并`：`可合并` 表示属于重复簇候选；`独立保留` 表示应单独存在
- `主落点 / 关联编号`：用于跨分组重复簇追踪主落点与关联规则
- `原 Skill`：旧规则来源 Skill
- `原规则原文`：旧 Skill 中的原始规则片段
- `新归属 Skill`：建议落点 Skill
- `建议新正文 / 备注`：统一使用 `建议正文：...` 或 `迁移备注：...`
- `迁移状态`：最终统一收口为 `已完成`

## 代码规范

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CS-01 | 代码规范 | 约束 | 独立保留 | 主落点 | code-standards | 目标平台: MicroPython（RT1021）, 本地开发兼容 Python 3.8+ | using-rules | 建议正文：目标平台是 RT1021 + MicroPython, 本地开发兼容 Python 3.8+ | 已完成 |
| CS-02 | 代码规范 | 约束 | 独立保留 | 主落点 | code-standards | 类型提示必须完整, 避免 `Any`, 返回值类型要显式 | using-rules | 建议正文：类型提示必须完整, 避免 `Any`, 返回值类型必须显式 | 已完成 |
| CS-03 | 代码规范 | 约束 | 独立保留 | 主落点 | code-standards | 运行时代码默认不要依赖 `typing` 模块, 如需类型辅助, 优先使用不影响板端导入的兼容写法 | using-rules | 建议正文：运行时代码默认不要依赖 `typing`, 如需类型辅助, 优先使用不影响板端导入的兼容写法 | 已完成 |
| CS-04 | 代码规范 | 约束 | 独立保留 | 主落点 | code-standards | 注释与文档字符串统一使用中文<br>文档注释统一采用 Doxygen 风格 | using-rules | 建议正文：注释与文档字符串统一使用中文, 文档注释统一采用 Doxygen 风格 | 已完成 |
| CS-05 | 代码规范 | 约束 | 独立保留 | 主落点 | code-standards | 注释标点使用半角符号并保留空格规则<br>单行注释行尾不加收尾标点 | using-rules | 建议正文：注释标点统一使用半角符号并保持空格规则, 单行注释行尾不加收尾标点 | 已完成 |
| CS-06 | 代码规范 | 约束 | 可合并 | 主落点 | code-standards | 当一个领域模块需要拆成 2 个以上内部实现文件时, 必须优先改为包目录加 `__init__.py`<br>禁止使用共同前缀平铺文件模拟命名空间<br>单一领域出现 2 个以上共同前缀平铺文件时优先收拢为分包 | using-rules | 迁移备注：分包规则重复簇, 与 `AB-02` 一起复核文件组织边界 | 已完成 |
| CS-07 | 代码规范 | 约束 | 可合并 | 主落点, 关联 `RV-03` | code-standards | 魔法数字集中到 `config/params.py`<br>关键参数统一在 `config/params.py`, 禁止散落阈值 | using-rules | 建议正文：参数与阈值统一集中到 `config/params.py` | 已完成 |
| CS-08 | 代码规范 | 约束 | 独立保留 | 主落点 | code-standards | 禁止静默失败, 只捕获预期异常并保留上下文 | using-rules | 建议正文：禁止静默失败, 只捕获预期异常并保留上下文 | 已完成 |

## 架构边界

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AB-01 | 架构边界 | 约束 | 独立保留 | 主落点 | code-standards | `hardware/`、`control/`、`filters/`、`storage/`、`config/`、`utils/` 的目录职责定义 | using-rules | 建议正文：目录分层职责必须固定, 各层只承担本层责任 | 已完成 |
| AB-02 | 架构边界 | 约束 | 可合并 | 主落点 | code-standards, control-system | `services/`: 编排层, 连接硬件、控制与领域子系统<br>`services/` 只负责编排, 不承载底层算法细节或驱动细节<br>业务编排混入驱动层或算法层时必须上移到 `services/` | using-rules | 建议正文：`services/` 只做编排, 不承载算法、驱动细节或隐藏状态机 | 已完成 |
| AB-03 | 架构边界 | 约束 | 独立保留 | 主落点 | code-standards | `vision/` 或独立领域包负责视觉协议、状态机和领域转换逻辑, 不混入服务编排细节 | using-rules | 建议正文：视觉与独立领域逻辑不得混入服务编排细节 | 已完成 |
| AB-04 | 架构边界 | 约束 | 独立保留 | 主落点 | code-standards | 允许与禁止的依赖方向, 包括禁止下层依赖上层、禁止循环依赖、禁止跨层跳跃调用 | using-rules | 建议正文：依赖方向与跨层调用规则必须统一收口 | 已完成 |
| AB-05 | 架构边界 | 约束 | 独立保留 | 主落点 | code-standards | 一个运行时状态只能有一个主拥有者<br>模块协作必须通过显式接口、受控数据结构或明确协议完成 | using-rules | 建议正文：状态所有权必须唯一, 协作必须显式化 | 已完成 |
| AB-06 | 架构边界 | 约束 | 独立保留 | 主落点 | code-standards | handler、query、facade、adapter 只能通过受控上下文接口协作, 不得直接耦合宿主私有字段 | using-rules | 建议正文：handler / facade / adapter 只能通过显式上下文接口协作 | 已完成 |

## 内存门禁

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MB-01 | 内存门禁 | 评审 | 独立保留 | 主落点 | code-standards | 对 `TransportCar`、运行时 owner、诊断 facade、命令装配和板端 probe 的改动, review 一号目标是最小内存占用指标, 不是结构整洁度 | project-extension-requesting-code-review | 建议正文：收口评审时, 最小内存占用指标优先于结构整洁度 | 已完成 |
| MB-02 | 内存门禁 | 约束 | 独立保留 | 主落点 | code-standards | import-time 自动注册必须 fail-fast、可观测、可验证<br>import-time 禁止目录扫描、自动发现、自动注册和重型单例初始化 | using-rules | 建议正文：import-time 副作用必须可见且受限 | 已完成 |
| MB-03 | 内存门禁 | 评审 | 独立保留 | 主落点 | code-standards | 新增常驻对象必须说明 owner、阶段、分类、触发条件和必要性 | project-extension-requesting-code-review | 建议正文：新增常驻对象必须说明 owner、阶段、分类、触发条件和必要性 | 已完成 |
| MB-04 | 内存门禁 | 评审 | 独立保留 | 主落点 | code-standards | 模块级可变运行时全局状态属于阻断项<br>可延迟功能若被重新放回构造期无条件初始化, 直接视为不通过 | project-extension-requesting-code-review | 建议正文：模块级可变全局状态与错误的构造期初始化都属于阻断项 | 已完成 |
| MB-05 | 内存门禁 | 评审 | 独立保留 | 主落点 | code-standards | 热路径新增大字符串拼接、大临时容器或无解释动态分配时, 必须提供必要性证明<br>结构更清晰但内存指标未改善, 不算有效重构<br>必须给出关键内存证据 | project-extension-requesting-code-review | 建议正文：热路径动态开销必须证明必要性, 并附内存证据 | 已完成 |

## 嵌入式流程

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ED-01 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | 核心原则：行为改动必须先有失败测试 | using-rules | 建议正文：行为改动必须先选测试层, 并先有失败测试 | 已完成 |
| ED-02 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | 涉及 PID、运动学、里程计或轨迹行为时, 追加 `control-system` | using-rules | 建议正文：触及 PID、运动学、里程计或轨迹行为时追加控制系统规则 | 已完成 |
| ED-03 | 嵌入式流程 | 流程 | 可合并 | 主落点 | embedded-development | 纯逻辑与确定性行为优先 `tests/unit/`<br>命令、协议与副作用契约优先 `tests/contract/`<br>硬件路径必须进入 `tests/hil/` | using-rules | 建议正文：测试层选择按 `tests/unit`、`tests/contract`、`tests/hil` 三层固定执行 | 已完成 |
| ED-04 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | RED -> GREEN -> REFACTOR, 并确认失败原因、通过范围与覆盖缺口 | using-rules | 建议正文：测试驱动开发步骤固定为 RED -> GREEN -> REFACTOR | 已完成 |
| ED-05 | 嵌入式流程 | 流程 | 可合并 | 主落点, 关联 `ED-17` | embedded-development | 修改 `src/hardware/`<br>修改 `src/services/transport_car.py`<br>依赖真实串口、编码器、IMU、电机、ticker、板端状态<br>需要证明 5ms 预算、方向一致性、传感器稳定性、真实动作链路 | using-rules | 建议正文：满足任一条件即进入设备路径 | 已完成 |
| ED-06 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | 若不触及设备路径, 可在主机侧验证通过后结束 | using-rules | 建议正文：只有不触及设备路径时, 才能在主机侧验证通过后结束 | 已完成 |
| ED-07 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | `stage2` 只验证连接、同步、导入、安全探针与最小查询链路, 不验证真实硬件动作 | using-rules | 建议正文：`stage2` 只做最小运行与 smoke 验证, 不验证真实硬件动作 | 已完成 |
| ED-08 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | `stage2` 默认先执行 `mpy-cli plan`, 再执行 `mpy-cli upload/run/delete`, 并运行安全 smoke 探针 | using-rules | 建议正文：`stage2` 默认命令顺序固定为 `mpy-cli plan` -> `mpy-cli upload/run/delete` -> smoke 探针 | 已完成 |
| ED-09 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | `stage2` 必验项：设备可连接、文件可上传执行、模块可导入、query / smoke 已注册、安全模式入口可见可用 | using-rules | 建议正文：`stage2` 必验项必须逐项确认 | 已完成 |
| ED-10 | 嵌入式流程 | 约束 | 独立保留 | 主落点 | embedded-development | `stage2` 禁止直接启动真实电机、真实编码器动作链路、真实 IMU 动作链路<br>不得把 `stage2` 失败当成“板子问题”直接跳过 | using-rules | 建议正文：`stage2` 禁止启动真实动作链路, 也不得因失败直接跳过 | 已完成 |
| ED-11 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | `stage3` 通过 `uart3` 做人工联调与故障归因, `uart6` 保持正式通信链路, 读取 `health/tick/imu/enc/motor/vision` 等快照 | using-rules | 建议正文：`stage3` 用于人工联调与归因, `uart6` 保持正式链路 | 已完成 |
| ED-12 | 嵌入式流程 | 流程 | 独立保留 | 主落点 | embedded-development | `stage3` 由人和 AI 在环分析, 不是自动 PASS / FAIL 阶段, 必须确认状态可读且失败可归因 | using-rules | 建议正文：`stage3` 是人工联调阶段, 不是自动 PASS / FAIL 阶段 | 已完成 |
| ED-13 | 嵌入式流程 | 流程 | 可合并 | 主落点, 关联 `CT-02`, `RV-03` | embedded-development | 关键实时约束未被破坏<br>尤其是 5ms 控制周期预算<br>若控制周期超预算, 先降复杂度, 再讨论新特性 | using-rules | 建议正文：5ms 控制周期预算属于实现阶段硬约束, 超预算先降复杂度 | 已完成 |
| ED-14 | 嵌入式流程 | 流程 | 可合并 | 主落点, 关联 `ED-17` | embedded-development | `tests/hil/` 必须留下步骤、预期、实测与 PASS / FAIL 结论, 作为最终完成证据 | using-rules | 建议正文：`tests/hil/` 中必须留下完整留证记录 | 已完成 |
| ED-15 | 嵌入式流程 | 交付 | 独立保留 | 主落点 | embedded-development | 进入设备路径后的交付物必须包含主机测试、设备命令、smoke 输出、观测输出、失败归因和 HIL 证据 | project-extension-requesting-code-review | 建议正文：进入设备路径后, 交付物必须包含主机测试、设备命令、smoke 输出、观测输出、失败归因和 HIL 证据 | 已完成 |
| ED-16 | 嵌入式流程 | 评审 | 独立保留 | 主落点 | embedded-development | 不允许先写完再补测试<br>不允许主机测试过了就不上板<br>不允许直接让车动一下看看<br>不允许跳过 `stage2` 直接看 `stage3`<br>不允许看到串口有输出就算完成<br>不允许 HIL 以后再补 | project-extension-requesting-code-review | 建议正文：以上 6 条收口禁令只能留在评审侧 | 已完成 |

## 硬件事实

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HF-01 | 硬件事实 | 事实 | 独立保留 | 主落点 | embedded-development | 已知 `src/boot.py` 的 Button 1-4 板级引脚分别为 `C8`、`C9`、`C14`、`C15` | using-rules | 建议正文：Button 1-4 板级引脚分别为 `C8`、`C9`、`C14`、`C15` | 已完成 |
| HF-02 | 硬件事实 | 事实 | 独立保留 | 主落点 | embedded-development | 已知 `src/boot.py` 的 D8/D9 角色输入带上拉电阻, 读到 `1` 表示开关关闭, 读到 `0` 表示开关闭合 | using-rules | 建议正文：D8/D9 角色输入带上拉电阻, `1` 表示开关关闭, `0` 表示开关闭合 | 已完成 |

## 视觉语义

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VS-01 | 视觉语义 | 事实 | 独立保留 | 主落点 | embedded-development | 以 `docs/Protocol.md`、`src/services/vision_protocol.py`、`src/services/vision_state_machine.py` 为准<br>`src/control/kinematics.py` 中“X 前 / Y 左”视为历史残留 | using-rules | 建议正文：视觉协议事实源以 `docs/Protocol.md` 与当前视觉实现为准 | 已完成 |
| VS-02 | 视觉语义 | 事实 | 可合并 | 主落点 | embedded-development | `y+` = 前进<br>`x+` = 右移<br>`omega+` / `d_angle+` = 顺时针<br>`dx/dy/d_angle` 是车体系相对增量<br>`x/y/angle` 是世界系绝对目标 | using-rules | 建议正文：坐标系、正方向和相对 / 绝对量定义必须集中保留 | 已完成 |
| VS-03 | 视觉语义 | 事实 | 可合并 | 主落点 | embedded-development | 视觉输入只认 `UART6` 上完整框 `left,top,right,bottom`<br>旧 `x,y` 或混合载荷会被视觉协议吞掉<br>最终画面坐标已完成翻转处理, 主控侧不得再次翻转 | using-rules | 建议正文：视觉输入字段与翻转语义必须统一定义 | 已完成 |
| VS-04 | 视觉语义 | 约束 | 独立保留 | 主落点 | embedded-development | 对正状态与推行状态的符号关系, 包括 `ALIGN_ANGLE`、`ALIGN_DX`、`ALIGN_DIST`、`ORBITING`、`PUSHING`、`RETURNING` | using-rules | 建议正文：对正与推行状态的符号关系必须集中定义 | 已完成 |
| VS-05 | 视觉语义 | 约束 | 独立保留 | 主落点, 关联 `ED-14` | embedded-development | `push_angle_deg = -90` 只能解释为相对当前复位零点的绝对航向目标<br>没有 HIL 证据前, 不要口头改写成“朝左 / 朝右 / 朝前 / 朝后” | using-rules | 建议正文：绝对方向描述必须受 HIL 证据约束 | 已完成 |
| VS-06 | 视觉语义 | 约束 | 独立保留 | 主落点 | embedded-development | 说“左 / 右 / 前 / 后 / 顺时针 / 逆时针”时必须标明参考系 | using-rules | 建议正文：任何方向描述都必须明确参考系 | 已完成 |
| VS-07 | 视觉语义 | 事实 | 独立保留 | 主落点 | embedded-development | 当前视觉链路默认采用斜俯视类人视角, 目标默认位于地板平面, 因而 `bottom` 可作为接近程度代理量 | using-rules | 建议正文：`bottom` 代理量的成立前提必须明确保留 | 已完成 |
| VS-08 | 视觉语义 | 流程 | 独立保留 | 主落点 | embedded-development | 联调前检查包括：查询 `?vision`、确认 `obs_center_x` 和 `obs_bottom` 变化方向、确认 `ALIGN_ANGLE -> ALIGN_DIST -> ALIGN_DX` 阶段顺序、确认旧 `x,y` 不再误入普通控制链路 | using-rules | 建议正文：联调前检查项必须成组执行 | 已完成 |
| VS-09 | 视觉语义 | 流程 | 独立保留 | 主落点 | embedded-development | 若出现方向异常, 应先查 OpenArt 翻转、镜头安装方向、视觉发送格式、识别框字段顺序、车体坐标理解、电机方向、编码器方向, 不要靠改增益符号掩盖 | using-rules | 建议正文：方向异常必须按固定顺序排查, 不得用增益符号掩盖问题 | 已完成 |
| VS-10 | 视觉语义 | 流程 | 独立保留 | 主落点 | embedded-development | 输出结论前必须自检参考系、字段 / 控制量、阶段语义、相对量 / 绝对量 | using-rules | 建议正文：输出结论前必须完成语义自检 | 已完成 |
| VS-11 | 视觉语义 | 流程 | 独立保留 | 主落点 | embedded-development | `connect_failed`、`deploy_failed`、`probe_failed`、`observe_failed`、`hil_pending` 失败分类 | using-rules | 建议正文：联调输出必须使用统一失败分类 | 已完成 |

## 控制系统

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CT-01 | 控制系统 | 事实 | 可合并 | 主落点 | control-system | 控制层级：位置环（外环） -> 速度环（内环） -> PWM 输出<br>反馈来源：编码器（速度 / 里程计）+ IMU（航向）<br>模式：速度模式、位置模式、角度保持模式 | using-rules | 建议正文：控制层级固定为位置环 -> 速度环 -> PWM 输出, 并明确反馈来源与模式 | 已完成 |
| CT-02 | 控制系统 | 约束 | 可合并 | 主落点, 关联 `ED-13`, `RV-03` | control-system | 改算法前先确认硬件基线：编码器方向、电机方向、IMU 校准<br>参数辨识先行：使用 `pid_identify.py` 生成最新电机参数<br>控制周期预算默认 5ms，新增计算必须评估耗时 | using-rules | 建议正文：控制算法实现前置检查与 5ms 控制周期预算应一起保留 | 已完成 |
| CT-03 | 控制系统 | 流程 | 独立保留 | 主落点 | control-system | 调参流程：`calibrate_gyro.py` -> `pid_identify.py` -> 内环 -> 外环 -> 航向保持 -> 组合轨迹联调 | using-rules | 建议正文：控制系统调参流程必须固定化 | 已完成 |
| CT-04 | 控制系统 | 流程 | 独立保留 | 主落点 | control-system | 快速诊断：振荡、响应慢、稳态误差、航向漂移、轨迹偏差的排查顺序 | using-rules | 建议正文：控制问题应按固定诊断顺序排查 | 已完成 |
| CT-05 | 控制系统 | 评审 | 独立保留 | 主落点 | control-system | 单轮与三轮协同控制、模式切换、`?lock` 一致性、长时运行稳定性 | project-extension-requesting-code-review | 建议正文：控制系统收口验证必须覆盖协同控制、模式切换和长时稳定性 | 已完成 |

## Git 规范

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GT-01 | Git 规范 | 约束 | 可合并 | 主落点 | code-standards, control-system | 本项目 Git 规范只认 `.agents/skills/git-workflow/SKILL.md`<br>不要使用 superpowers 自带的 git workflow 作为本项目规范 | git-workflow | 建议正文：本项目 Git 规范只认 `.agents/skills/git-workflow/SKILL.md`, 不使用上游默认 git workflow | 已完成 |

## Skill 编写方法论

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WS-01 | Skill 编写方法论 | 约束 | 独立保留 | 主落点 | harness-design-pattern | `harness-design-pattern` 的正文与方法论不应继续作为用户主 review 正文 | project-extension-writing-skills | 建议正文：Harness 设计模式与写作方法论迁入 `references/writing-rules.md` | 已完成 |
| WS-02 | Skill 编写方法论 | 约束 | 独立保留 | 主落点 | harness-design-pattern, project-extension-writing-skills | 本仓库 Skill 命名、目录和 `references / assets` 约束应统一收口 | project-extension-writing-skills | 建议正文：命名、结构与引用规则统一并入 `references/writing-rules.md` | 已完成 |
| WS-03 | Skill 编写方法论 | 流程 | 独立保留 | 主落点 | project-extension-writing-skills | 旧 Skill 向新结构迁移时需要独立检查清单 | project-extension-writing-skills | 建议正文：迁移步骤与自检项保留在 `references/migration-checklist.md` | 已完成 |
| WS-04 | Skill 编写方法论 | 流程 | 独立保留 | 主落点 | harness-design-pattern, project-extension-writing-skills | Skill 重构时必须避免因合并入口或删除旧正文而丢规则 | project-extension-writing-skills | 建议正文：并表去向、条目落位与删除前确认统一写入 `references/migration-checklist.md` | 已完成 |

## 评审交付

| 规则编号 | 主题分类 | 规则类型 | 是否可合并 | 主落点 / 关联编号 | 原 Skill | 原规则原文 | 新归属 Skill | 建议新正文 / 备注 | 迁移状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RV-01 | 评审交付 | 评审 | 独立保留 | 主落点 | code-standards | 发现 God object、隐式上下文协议、状态双写或职责漂移时, 优先拆分状态所有权和协作边界, 不要继续堆补丁 | project-extension-requesting-code-review | 建议正文：架构健康问题必须在收口评审中明确指出并要求简化 | 已完成 |
| RV-02 | 评审交付 | 评审 | 独立保留 | 主落点 | code-standards | 没有 2 个以上真实消费者时, 不要引入通用框架式抽象<br>不要为了“未来可能扩展”提前引入事件总线、插件系统或多层适配器链 | project-extension-requesting-code-review | 建议正文：过度设计与伪扩展性都属于收口评审门禁 | 已完成 |
| RV-03 | 评审交付 | 评审 | 可合并 | 主落点, 关联 `CS-07`, `CT-02`, `ED-13` | code-standards | 收口检查包括：正确分层目录、无上层反向依赖、满足类型提示与中文文档要求、参数集中到 `config/params.py`、满足 5ms 控制周期约束 | project-extension-requesting-code-review | 建议正文：收口评审必须复核分层、参数集中与 5ms 控制周期约束 | 已完成 |
| RV-04 | 评审交付 | 评审 | 独立保留 | 主落点 | code-standards | 不要只给表面结论<br>必须明确职责边界、状态归属、耦合方式和抽象成本是否健康 | project-extension-requesting-code-review | 建议正文：收口结论必须回答边界、状态归属、耦合方式和抽象成本 | 已完成 |
| RV-05 | 评审交付 | 交付 | 独立保留 | 主落点 | code-standards | 交付物应包含代码或重构结果、关键验证步骤与结果记录、必要时提供简短变更说明 | project-extension-requesting-code-review | 建议正文：通用交付物必须包含结果、验证记录和必要的变更说明 | 已完成 |
| RV-06 | 评审交付 | 交付 | 独立保留 | 主落点 | control-system | 控制算法或参数变更说明<br>调参与验证记录（步骤 + 现象 + 结论）<br>必要时补充回归测试脚本或验证命令 | project-extension-requesting-code-review | 建议正文：控制系统交付物必须补充参数说明、调参与验证记录 | 已完成 |
