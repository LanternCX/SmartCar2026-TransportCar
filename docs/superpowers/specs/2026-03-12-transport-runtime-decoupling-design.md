# Transport 运行时完整解耦设计文档

## 背景

当前 `src/services/transport_car.py` 同时承担硬件装配, 周期调度, UART 收包, 命令状态, 视觉协调, 诊断快照等多类职责。`CommandRouter` 与 `commands/` 通过 `_finalize_route`、`_pending_dx`、`_query_response_uart` 等隐式私有字段协议与 `TransportCar` 协作, 导致 service 层边界不清, 状态归属混乱, 重构风险持续累积。

与此同时, `vision_protocol`、`vision_state_machine`、`vision_debug` 等模块虽然位于 `src/services/` 下, 但本质上已经形成独立的视觉领域子系统。继续将其放在 `services/` 内, 会放大“编排层成为杂物层”的问题。

## 目标

1. 完整解耦 `TransportCar`, 使其退化为运行时装配与调度入口。
2. 将视觉相关模块整体迁移到独立 `src/vision/` 包内。
3. 将命令状态, 底盘控制, 串口接入, 诊断聚合拆分为独立对象, 明确状态所有权。
4. 保持现有串口协议, 查询格式, 视觉吞包语义, 控制顺序和 host/HIL 表现不变。
5. 采用一步到位硬切方案, 最终仓库中不保留兼容壳, 不保留旧路径双轨。

## 非目标

1. 不修改外部通信协议, 不变更 `docs/Protocol.md` 已承诺的命令和查询语义。
2. 不在本次重构中引入事件总线, 通用插件框架或多余抽象层。
3. 不改变控制算法参数, 视觉状态机阈值和底盘实时预算目标。

## 设计原则

1. 状态只能有一个主拥有者, 禁止多个模块共享读写私有字段。
2. 编排层只负责连接子系统, 不保存底层算法细节状态。
3. 领域逻辑按职责归位, 不按“当前谁在调用”归位。
4. 优先显式接口和简单数据流, 避免为了未来假设需求过度抽象。
5. 行为不变优先于结构优雅, 任何架构收益都不能牺牲既有协议和控制语义。

## 目标目录结构

```text
src/
  hardware/
    uart_bus.py
    motors.py
    encoders.py
    imu.py

  control/
    chassis_state.py
    chassis_controller.py
    attitude_estimator.py
    wheel_speed_controller.py
    motion_planner.py
    kinematics.py
    pid_controller.py
    pid_math.py

  vision/
    protocol.py
    state_defs.py
    state_registry.py
    state_machine.py
    transforms.py
    debug.py
    coordinator.py

  services/
    transport_car.py
    commanding/
      router.py
      session.py
      context.py
      handlers/
    runtime/
      uart_ingress.py
      diagnostics_facade.py
```

## 核心对象职责

### `TransportCar`

- 创建并持有硬件对象与子系统对象。
- 驱动 tick 主循环和 stop 生命周期。
- 串联 `UartIngressService`、`VisionCoordinator`、`CommandSession`、`ChassisController`、`DiagnosticsFacade`。
- 不再持有命令暂存字段, 查询临时字段和视觉内部状态。

### `UartIngressService`

- 负责 `uart3` / `uart6` 非阻塞收包, 粘包拆包和来源标记。
- 优先将 `uart6` 上的视觉帧送入 `VisionCoordinator`。
- 将 query token 交给命令查询入口, 将普通命令批次交给 `CommandSession`。
- 统一错误捕获与结构化错误记录。

### `CommandSession`

- 负责人工命令语义和 lock 生命周期。
- 维护 `last_cmd`、相对位移意图, rear 模式状态和 reset 语义。
- 向外暴露显式接口, 如 `apply_batch()`、`build_control_request()`、`reset()`。
- 不再允许 handler 直接写宿主对象私有字段。

### `ChassisController`

- 负责轮速滤波, IMU 姿态更新, 里程计更新, 位置/角度控制和逆运动学。
- 合并手动控制请求与视觉控制请求, 生成三轮目标速度和电机 duty。
- 负责 rear only 模式下的目标速度分配和锁定动作解锁判定。
- 成为底盘控制运行时状态的唯一拥有者。

### `VisionCoordinator`

- 负责视觉观测缓存, 视觉状态机推进和视觉目标快照。
- 提供 `accept_line()`、`step()`、`current_request()`、`snapshot()` 等显式接口。
- 不直接依赖 `TransportCar`, 只消费标量输入和时间戳。

### `DiagnosticsFacade`

- 聚合 `CommandSession`、`ChassisController`、`VisionCoordinator` 的只读状态。
- 构造 `health/tick/imu/enc/motor/vision/pos/lock/log` 查询输出。
- 统一 query 响应串口选择与格式化。

## 状态所有权

| 状态 | 主拥有者 | 备注 |
| :--- | :--- | :--- |
| `last_cmd` / lock / rear 模式 | `CommandSession` | 命令协议与动作生命周期 |
| `_pending_dx/_dy/_d_angle` | `CommandSession` | 只保留在命令会话内部 |
| 轮速滤波, PID, 目标速度, duty | `ChassisController` | 底盘控制运行态 |
| `heading_est` / `heading_target` / yaw PID 积分 | `ChassisController` | 姿态与角度控制态 |
| 里程计 `x/y` | `ChassisController` | 控制层世界坐标状态 |
| 视觉观测缓存, 状态机状态, 视觉目标 | `VisionCoordinator` | 视觉领域运行态 |
| query 响应目标串口 | `DiagnosticsFacade` / query 上下文 | 不再借助宿主临时私有字段 |

## 关键运行链路

### UART 输入链路

1. `TransportCar.step()` 调用 `UartIngressService.poll()`。
2. `uart6` 新行先尝试送入 `VisionCoordinator.accept_line()`。
3. 若视觉协议消费成功, 命令链不再处理该行。
4. `?token` 类查询进入 query 入口并回写到来源串口。
5. 普通控制命令解析为命令批次后交给 `CommandSession.apply_batch()`。

### Tick 控制链路

1. `TransportCar` 在 tick 到达后先调用 `VisionCoordinator.step()`。
2. 再由 `ChassisController.step()` 完成轮速读取, 姿态更新, 里程计更新和控制输出。
3. `ChassisController` 从 `CommandSession` 和 `VisionCoordinator` 获取当前控制请求。
4. `DiagnosticsFacade` 对外暴露最新快照。

### Query 链路

1. query handler 不再直接触碰 `TransportCar` 字段。
2. query handler 只依赖显式上下文接口和快照构造器。
3. 未知 query 仍返回 `?unknown=<token>`。

## 必须保持不变的行为契约

1. `UART6` 上合法完整视觉帧优先被视觉协议消费, 不得落入普通命令链。
2. 旧 `x,y` 视觉载荷和混合畸形视觉载荷仍需被吞掉, 不得误驱动车模。
3. query 必须回写到收到该查询的同一串口。
4. `reset` 必须继续支持裸命令和大小写变体, 且不受 lock 限制。
5. `rear` 模式变更仍触发 lock, 完成动作后自动恢复全向并停车。
6. 视觉目标激活时继续优先于手动位置目标。
7. tick 内部顺序继续保持“视觉刷新在前, 姿态/里程计/控制在后”。
8. `?vision`、`?health`、`?tick`、`?imu`、`?enc`、`?motor`、`?pos`、`?lock` 输出格式不变。
9. 控制周期预算仍以 5ms 为目标, 不能引入阻塞式 I/O 或过度动态分配。

## 迁移策略

采用硬切但分阶段受测的迁移方式：

1. 先补保护网, 锁定 contract / unit / HIL 外部行为。
2. 再引入新对象和新目录, 但每一步都以显式接口替代隐式私有字段协议。
3. 在所有调用点切换完成后, 删除旧方法, 旧字段和旧模块路径。
4. 合并前确保仓库内不再存在 `services/vision_*.py` 双轨和 `TransportCar` 内部临时兼容逻辑。

## 测试策略

### Host TDD

- `tests/contract/services/` 先锁 UART 协议, query 路径和命令语义。
- `tests/unit/services/` / `tests/unit/vision/` 锁视觉状态机, 协调器, 底盘控制内部逻辑。
- `tests/unit/control/` 新增底盘控制子模块测试。

### Device Path

- 由于触及 `src/services/transport_car.py`, 必须按 `stage1 -> stage2 -> stage3 -> HIL` 执行。
- `Stage 2` 验证最小导入, query 链路与 diagnostic mode。
- `Stage 3` 验证 `uart6` 持续视觉流, `uart3` 查询并发和实时预算。
- `tests/hil/` 记录视觉对齐, reset 打断, rear 模式, tick overrun 等证据。

## 验收标准

1. `TransportCar` 不再保存命令内部状态, 视觉内部状态和 query 临时字段。
2. 视觉模块全部位于 `src/vision/`。
3. 命令 handler 只能通过显式上下文接口工作, 不再读写宿主私有字段。
4. `control` 成为底盘控制和状态估计的主承载层。
5. Host 测试, Stage 2, Stage 3 和 `tests/hil/` 证据均表明行为无回归。
