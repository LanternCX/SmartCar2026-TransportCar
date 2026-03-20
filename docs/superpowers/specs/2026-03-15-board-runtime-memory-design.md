# 板端全流程内存优化设计

## 目标

面向当前仓库 `src/` 的板端运行时代码, 对启动期, 初始化期, 运行期和诊断期做统一内存治理, 降低导入峰值, 减少常驻对象和高频分配, 并让低内存时仍能保留最小可观测性。

## 设计原则

- import-time 只定义代码, 不做重装配
- 运行时状态单一 owner, 禁止重复副本
- 高频路径优先固定槽位和复用缓冲
- 低优先级日志 best-effort, query 优先于日志
- 系统先保证可启动, 可查询, 可判断, 再拉起完整功能

## 一. 启动期优化

### 问题

- 当前已出现 `services.commanding.handlers.__init__` 在自动发现阶段 OOM
- 目录扫描, 排序, 模块名拼装和批量导入会抬高导入期峰值

### 方案

- 去掉 handler 自动发现
- 改为静态显式模块列表或按模式显式加载
- 模块导入时不执行全量注册和重型装配
- `services.transport_car` 不在 import-time 触发高开销逻辑

### 目标

- `import services.transport_car` 不应触发目录扫描和批量字符串聚合
- 启动期导入链内存峰值显著下降

## 二. 初始化期优化

### 方案

- 初始化拆为两段:
  - `core init`: uart, 最小 logger, chassis state, 最小 query 能力
  - `feature init`: vision, 完整 handler, 扩展 diagnostics, 可选调试能力
- 非关键对象延迟创建
- 主车和辅车按 role 只拉起必要子系统

### 目标

- 设备尽快进入“活着且可查询”的状态
- 完整功能装配不再一次性冲高内存峰值

## 三. 运行期优化

### 方案

- `TransportCar` 只做编排, 不重复持有子系统状态
- `vision` 保持 runtime owner + 固定槽位
- `diagnostics` 只读 owner, 不复制运行时状态
- `logger` 保持低分配快路径
- 清理高频 `closure/list/dict/string` 短生命周期分配

### 目标

- 主循环每拍分配最少
- 视觉链和日志链不再成为主要内存放大器

## 四. 诊断期优化

### 方案

- 最小诊断面固定保留 `?health`, `?tick`, `?vision`
- `?health` 保留轻量字段:
  - `alive`
  - `uptime_ms`
  - `vision_state`
  - `oom_count`
  - `oom_stage`
- 低内存时优先保留 query, 低优先级日志可退让

### 目标

- 在日志退让时仍可判断系统是否活着, 最近是否发生过 OOM, 视觉是否仍有输入

## 五. 模块级治理重点

- `src/services/commanding/handlers/`: 自动发现改显式装配
- `src/services/transport_car.py`: staged init, 收缩构造早期装配压力
- `src/diagnostics/`: 保持轻量常驻结构
- `src/vision/`: 保持 owner 收口, 禁止回退到多副本
- `src/services/runtime/`: 继续做 facade, 不复制运行时状态

## 六. 实施顺序

1. 先解决启动期 import OOM
2. 再做 staged init
3. 再扫运行期高频分配
4. 固化最小诊断面
5. 最后做板端 HIL 验证

## 七. 验收标准

- `remote_control.py` 经 `boot.py` 启动时不再在导入链 OOM
- 接通视觉链后不因日志和短分配轻易进入 OOM
- `?health/?tick/?vision` 在异常前后尽量保持可用
- 状态机停滞时可以区分输入缺失, 条件不满足和最近 OOM
- 主机 `tests/unit + tests/contract` 全绿, 板端补 HIL 证据
