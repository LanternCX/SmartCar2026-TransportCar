# 运行时代码 300 行门禁重构设计

## 背景

上一轮重构虽然完成了 `RuntimeCore`、`MinimalCommandRuntime`、`MotionRuntime`、`VisionRuntimeService` 和 `MinimalDiagnostics` 的 owner 下沉, 但 review 仍然不通过。根因不是“没有拆 owner”, 而是 `src` 运行时代码里仍有多个超长文件, 其中 `src/services/transport_car.py` 仍超过 1000 行, 导致 import 面、函数定义数量、字符串常量和兼容层都继续堆在单文件里。对于 MicroPython, 行数本身不是唯一指标, 但超长运行时代码文件通常意味着 import-time 依赖和常驻定义仍然过重。

本设计引入新的硬门禁: 本次 review 范围内, 受约束的 `src` 运行时代码 Python 文件都必须 `<= 300` 非注释代码行。这个门禁不是为了样式整洁, 而是为了强制把编排、解析、状态机和日志发射职责拆开, 进一步收缩 import 面和常驻定义密度。

同时, `src/vision/protocol.py` 与 `src/vision/state_machine.py` 虽然不再单独受 300 行 gate 卡死, 但仍要求继续按职责拆分。原因不是行数, 而是这两处仍然承载多职责逻辑, 若继续保留大文件, 会让规范在 `services.car` 与 `vision/` 之间失衡。

## 目标

- 让 `src` 下当前所有超 300 行的运行时代码文件全部下降到 `<= 300` 行
- 统一公开入口到 `services.car`, 用真正的分包替代 `transport_*` 前缀平铺模块
- 继续把 `TransportCar` 降成薄壳 facade, 只保留公开入口和最小 wiring
- 在不回退 owner 架构的前提下, 进一步降低 import-time 定义密度和编排耦合

## 范围

本次强制门禁只适用于 `src` 运行时代码, 不包含 `tests`。

当前重点拆分文件:

- `src/services/transport_car.py`
- `src/services/runtime/diagnostics_facade.py`
- `src/vision/protocol.py`
- `src/vision/state_machine.py`
- `src/diagnostics/manager.py`

## 非目标

- 不在本轮把测试文件也全部压到 300 行内
- 不为了兼容保留 `transport_*` 平铺实现壳文件
- 不为拆分而引入插件系统、事件总线或多层抽象链
- 不用“行数达标”替代板端内存指标; 行数门禁只是新的结构约束

## 方案比较

### 方案 1: `services.car` 真正分包（采用）

把当前 `transport_car.py` 和 `transport_*` 平铺 helper 收进 `src/services/car/` 包, 对外统一公开 `services.car`。优点是 review 指向的问题能一次解决, `services/` 根目录不再靠前缀模拟命名空间, 内部文件名也能直接回到 `core.py`、`loop.py`、`vision.py`、`compat.py`、`bootstrap.py` 这种按职责命名。

### 方案 2: 保留 `services.transport_car`, 只把单文件改成包

回归风险更低, 但 review 已明确指出 `transport` 前缀本身就是问题, 即使变成包也仍然像是旧命名包袱, 不适合作为本轮最终结构。

### 方案 3: 只拆 `transport_car.py`

只能解决最显眼的单文件问题, 但 `src` 里仍有 4 个超限文件, review 依然过不了, 因此不可接受。

## 总体架构

### `src/services/car/`

对外入口统一为 `services.car`, 包内结构为:

- `src/services/car/__init__.py`: 公开入口与兼容导出
- `src/services/car/core.py`: `TransportCar` facade, public lifecycle, 时间 helper
- `src/services/car/bootstrap.py`: 初始化、lazy wiring、handler 装配入口
- `src/services/car/loop.py`: `step()`、tick 主循环、控制调度
- `src/services/car/vision.py`: 视觉 poll、目标刷新、状态机输入仲裁
- `src/services/car/compat.py`: 历史兼容桥接与 ingress 接线

其中 `core.py` 目标行数仍为 `<= 300`, 且 `src/services/` 根目录不再保留 `transport_*` 平铺模块。

### `src/services/runtime/diagnostics_facade.py`

改为 facade 薄壳, 只拼装各类 snapshot builder, 不再容纳所有 snapshot 细节。

新增子模块:

- `src/services/runtime/diag_format.py`
- `src/services/runtime/diag_health.py`
- `src/services/runtime/diag_motion.py`
- `src/services/runtime/diag_vision.py`

### `src/vision/protocol.py`

保留公开 `VisionProtocol`、`VisionFrame`、`VisionObservation` 等入口, 但把查询、解析、batch 提交拆开。这里的目标从“压到 300 行”改为“去除多职责 God module”, 保持统一的职责边界和注释风格。

新增分包:

- `src/vision/protocol/__init__.py`
- `src/vision/protocol/query.py`
- `src/vision/protocol/parse.py`
- `src/vision/protocol/batch.py`

### `src/vision/state_machine.py`

保留公开类型和状态机入口, 把状态转移和 action 计算拆到辅助模块。这里同样以职责分离和注释可维护性为主, 不再单独以 300 行 gate 作为唯一目标。

新增分包:

- `src/vision/state_machine/__init__.py`
- `src/vision/state_machine/types.py`
- `src/vision/state_machine/core.py`
- `src/vision/state_machine/actions.py`

### `src/diagnostics/manager.py`

保留公开 `LogManager`、`Logger` 和 `build_uart3_logger_manager()`, 把配置、emit 和 logger wrapper 拆开。

新增子模块:

- `src/diagnostics/log_config.py`
- `src/diagnostics/log_emit.py`
- `src/diagnostics/log_logger.py`

## 拆分规则

- 每个新文件目标控制在 `220-280` 行, 给后续改动留余量
- 新包入口允许只做受控导出, 但不得重新堆成第二个 God object
- 不得把已下沉 owner 搬回 `TransportCar`
- 不得引入 import-time 自动发现、自动注册或目录扫描
- 兼容层必须尽量实例级转发, 避免 class-level compatibility property 回潮
- `services/` 根目录只保留稳定领域包或稳定单模块, 不再用统一前缀模拟分组
- 当一个领域模块需要拆成多个实现文件时, 应优先收拢为分包, 不得继续使用共同前缀平铺文件模拟命名空间

## 测试策略

- 严格 TDD: 每个拆分点先写失败测试, 再搬实现
- 增加结构门禁测试, 锁定 `services.car` 包存在且 `src/services/` 根目录不存在 `transport_*.py`
- 更新行数门禁测试, 只扫描仍受 300 非注释代码行约束的运行时文件
- 为 `vision.protocol` / `vision.state_machine` 增加布局测试, 锁定拆分后子模块结构不回弹
- 每个模块拆分后先跑 targeted tests
- 最终运行 `python3 -m pytest tests/unit tests/contract -q`

## 验收标准

- 受门禁约束的 `src` 运行时代码文件全部 `<= 300` 非注释代码行
- `src/vision/protocol.py` 与 `src/vision/state_machine.py` 完成职责拆分, 且公开入口保持兼容
- 现有 host 侧 unit / contract 测试仍然通过
- `TransportCar` 继续只承担 facade / wiring 职责, 不回退成 God object
- `src/services/` 根目录不再保留 `transport_*` 平铺模块
- 不新增 import-time 自动装配和模块级可变全局
- 板端控制口恢复后, 再继续 Stage 2 / HIL 内存验收
