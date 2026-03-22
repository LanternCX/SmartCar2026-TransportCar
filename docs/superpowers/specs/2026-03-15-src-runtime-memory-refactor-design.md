# src 运行时代码低内存重构设计

## 日期
2026-03-15

## 目标

在不改变当前仓库 `src/` 对外命令协议, 板端使用方式和主辅车语义的前提下, 对所有实际上会上线的运行时代码做一次 repo 级内存审查与结构重构, 彻底清理不必要的模块级全局变量, 常驻对象, 重复缓存和高频短生命周期分配, 降低板端 OOM 风险, 并避免继续堆史山。

## 范围

- 仅包含当前仓库 `src/` 下的运行时代码
- 不包含 `tests/`, `docs/`, `.agents/skills/` 和兄弟仓库 `../SmartCar2026-Vision`
- 会同时覆盖高风险重点区与其余运行时代码:
  - `src/diagnostics/`
  - `src/vision/`
  - `src/services/`
  - `src/control/`
  - `src/filters/`
  - `src/storage/`
  - `src/hardware/`
  - `src/config/`
  - `src/utils/`

## 设计原则

### 1. 除真正常量外, 模块级不保留多余状态

- 不在模块导入时创建不必要的 `dict`, `list`, `tuple`, 字符串映射表或缓存对象
- 不保留只为代码结构说明存在的运行时辅助类或占位协议类
- 能用简单分支表达的逻辑, 不用全局映射表长期常驻

### 2. 运行时状态必须有单一 owner

- 同一个运行时状态只能由一个对象持有并负责更新
- 禁止多个模块同时缓存同一份派生结果或副本数据
- 诊断, 查询, 日志, 编排层只按需读取 owner, 不长期复制状态

### 3. 高频路径优先低分配

- 先判是否需要执行, 再创建日志文本或中间对象
- 优先固定槽位和可复用缓冲, 避免每拍动态拼装 `dict/list`
- 优先原地覆写和短路径分支, 避免中间层反复搬运数据

### 4. 不保留无价值兼容层

- 不同时长期维护新旧两套内部结构
- 能删掉的历史字段, 历史缓存和历史中间对象直接删除
- 不为了“以后可能用到”保留临时兼容代码

## 总体架构方向

### A. logger 与 diagnostics 先瘦身

日志系统是全局常驻基础设施, 当前已经证明会直接参与 OOM。重构目标不是少打一点日志, 而是让 logger 自身实现更小, 更少状态, 更少中间对象。

目标调整:

- `src/diagnostics/manager.py` 不再保留不必要的模块级映射表, 占位协议类和重复派生状态
- `LogManager.emit()` 直接处理最少输入, 避免构造额外中间对象
- `Logger` 改为真正轻量化并可缓存, 避免重复创建
- 高频日志先做等级与模块过滤判断, 再决定是否格式化文本
- 低内存态下, 高频日志直接退让或丢弃, 不再持续制造 `log.oom`

诊断相关模块同步收缩:

- `src/diagnostics/format.py` 改为更短格式化链路
- `src/diagnostics/sink.py` 保留最少写出路径
- `src/services/runtime/diagnostics_facade.py` 只按需读取 owner 状态, 不自行长期保存副本

### B. vision 改为单 owner

视觉链路当前最容易出现跨模块重复持有, 高频小对象和动态容器分配。重构目标是把视觉运行时状态收口到单一 owner, 让 `TransportCar` 只负责编排。

目标调整:

- 统一一个视觉运行时 owner 持有:
  - 最新观测
  - pending frame
  - 两路相机槽位
  - selected input
  - resolved target
  - 可复用 snapshot 缓冲
- 两路相机改为固定槽位, 不再每拍动态构造 `camera_frames` 之类的临时容器
- 协议解析, 帧缓存和状态机输入选择全部围绕 owner 展开
- `TransportCar` 不再重复缓存视觉派生状态

兼容要求:

- 保持当前命令协议和查询语义不变
- 保持主辅车角色语义不变
- 保持板端使用入口不变

### C. TransportCar 收缩为编排层

`src/services/transport_car.py` 当前是多子系统状态的汇聚点。重构后它应只承担编排职责, 不长期持有本该归属子系统 owner 的派生状态和中间缓存。

目标调整:

- 下放视觉运行时状态到视觉 owner
- 下放日志相关实现细节到 diagnostics owner
- 查询和诊断按需读取 owner, 不在 `TransportCar` 侧复制
- 清理历史字段, 冗余缓存, 和仅用于过渡的中间方法

### D. 对整个 `src/` 做逐文件内存审查

除了 logger 与 vision 两个重点区, 其余所有会上线的运行时代码也要统一执行清查。

每个文件都按同一套标准检查:

- 是否存在不必要的模块级全局变量
- 是否存在重复缓存和派生状态副本
- 是否在导入期创建无必要常驻对象
- 是否存在只增加层数, 但不减少复杂度的 helper / wrapper
- 是否存在高频路径短生命周期对象分配
- 是否存在多个模块共同持有同一份状态

## 模块级重构重点

### `src/diagnostics/manager.py`

- 删除不必要的运行时协议占位类
- 删除不必要的全局映射表与重复字符串常量
- 收缩 `LogManager` 和 `Logger` 的常驻字段
- 让高频路径变成低分配直通路径

### `src/diagnostics/format.py` / `src/diagnostics/sink.py`

- 保留最小格式化和最小写出链路
- 常见无色 ASCII 文本优先走最便宜路径
- 低内存时高频日志直接退让

### `src/vision/*.py`

- 重构成单 owner + 固定槽位模型
- 去掉跨模块重复持有的帧, 观测, 目标, 选择结果
- 去掉每拍动态 `dict/list` 拼装

### `src/services/transport_car.py`

- 收缩为编排器
- 删除不属于编排层 owner 的中间状态
- 删除为兼容历史路径留下的重复访问点

### `src/services/runtime/uart_ingress.py` / `src/services/commanding/*`

- 收短数据流
- 删除不必要的中间对象与历史兼容状态

### `src/control/*`, `src/filters/*`, `src/storage/*`, `src/hardware/*`, `src/config/*`, `src/utils/*`

- 做逐文件常驻内存与全局变量清查
- 清掉明显无必要的模块级展开和 wrapper 结构
- 保持行为稳定, 不做与内存目标无关的装饰性重写

## 执行顺序

### 阶段 1: 先瘦 logger 与 diagnostics

原因:

- 它们是全局常驻基础设施
- 当前已知会直接参与 OOM
- 先瘦这一层, 后续其他模块重构时调试成本更可控

### 阶段 2: 重构 vision owner

原因:

- 它是当前高频对象和动态分配热点
- 它与 `TransportCar` 的边界清理后, 编排层才能真正收缩

### 阶段 3: 收缩 `TransportCar` 与相关 runtime 流程

- 把编排层不该持有的状态下放
- 收短 `uart_ingress`, `diagnostics_facade`, `commanding` 数据流

### 阶段 4: 对整个 `src/` 做逐文件审查与收尾

- 对所有上线运行时代码统一过 checklist
- 清理仍残留的不必要模块级全局和冗余中间层

## TDD 与验证策略

### TDD 原则

- 每个重构阶段都按 RED -> GREEN -> REFACTOR 执行
- 先写失败测试锁定结构和行为, 再改实现
- 不用“先重构再补测试”的方式推进

### 测试重点

- 锁定外部行为不变
- 锁定状态 owner 变化后的公开接口行为
- 锁定历史冗余字段, 冗余缓存和中间对象已经消失
- 锁定高频路径不再走历史分配链路

### 回归目标

- `tests/unit` 和 `tests/contract` 目标范围保持全绿
- 变更完成后, 对与运行时主路径相关的测试做集中回归

## 防止继续堆史山的约束

- 不保留无价值兼容层
- 不同时维护新旧两套内部结构
- 一个状态只能有一个 owner
- 发现双写或副本缓存立即收口
- 每个阶段结束都回看是否新增了新的模块级全局或临时过渡结构

## 预期产出

- `src/` 上线运行时代码做完一轮 repo 级内存审查与结构瘦身
- logger 模块常驻实现显著简化
- 视觉运行时收口为单 owner
- `TransportCar` 恢复为清晰编排层
- `docs/superpowers/memory/` 记录本轮 repo 级代码侧收敛结论
- 若完成后仍存在相同 OOM, 将更强地指向板子硬件, 固件或运行时内存状态异常
