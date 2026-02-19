---
name: architecture-guardian
description: Ensure high cohesion, low coupling, and maintainable architecture across the SmartCar codebase.
---

# Purpose
维护清晰的架构边界，确保代码库的高内聚低耦合特性，便于功能扩展、调试和维护。

# When to Use
- 添加新功能模块时
- 重构现有代码时
- 发现模块职责不清或耦合过紧时
- 代码审查和架构评审时

# Architecture Layers

## 1. Hardware Layer (`hardware/`)
**职责**：封装所有硬件接口，提供统一的抽象

**模块**：
- `uart_bus.py`：串口通信配置和管理
- `motors.py`：电机驱动接口
- `encoders.py`：编码器读取接口
- `imu.py`：IMU 传感器接口

**原则**：
- 每个硬件模块应该可以独立初始化和测试
- 提供清晰的接口抽象，隐藏硬件细节
- 不包含业务逻辑或控制算法
- 异常处理：硬件错误应该被捕获并转换为领域异常

## 2. Control Layer (`control/`)
**职责**：实现核心控制算法

**模块**：
- `pid_controller.py`：PID 控制器实现
- `pid_math.py`：PID 数学运算
- `kinematics.py`：运动学正逆解和里程计
- `wheel.py`：单轮控制封装
- `ident_tools.py`：参数辨识工具

**原则**：
- 算法应该是纯函数或只依赖自身状态
- 不直接访问硬件，通过参数传递获取数据
- 提供清晰的输入输出接口
- 关键算法应该有文档说明数学原理

## 3. Filter Layer (`filters/`)
**职责**：提供信号处理和滤波算法

**模块**：
- `lowpass_filter.py`：低通滤波器
- `spike_filter.py`：中值滤波器
- `diff_limit_filter.py`：差分限幅滤波器
- `dual_window_regression_filter.py`：双窗口线性回归滤波器

**原则**：
- 每个滤波器应该是独立的、可重用的
- 提供统一的接口（`update()` 方法）
- 滤波器之间可以组合使用
- 状态独立管理，避免全局状态

## 4. Service Layer (`services/`)
**职责**：协调硬件和控制算法，实现业务逻辑

**模块**：
- `transport_car.py`：车模核心单例类，主控制循环与跨命令协调（`_finalize_route`）
- `command_router.py`：命令路由器，装饰器注册模式，将聚合命令字符串分发到独立处理器
- `commander.py`：指令分词器，将原始命令行拆分为 (key, val) 二元组列表
- `commands/`：命令处理器包，**每条命令对应一个独立文件**

**`services/commands/` 包结构**：

```
services/commands/
├── __init__.py          register_commands(router) — 统一注册入口
├── cmd_vx.py            vx 速度指令
├── cmd_vy.py            vy 速度指令
├── cmd_omega.py         omega/w 角速度指令
├── cmd_x.py             x 坐标目标
├── cmd_y.py             y 坐标目标
├── cmd_angle.py         angle/yaw 绝对偏航角
├── cmd_dx.py            dx 相对位移（暂存，finalize 处理）
├── cmd_dy.py            dy 相对位移（暂存，finalize 处理）
├── cmd_d_angle.py       d_angle/dyaw/da 相对角度增量
├── cmd_rear.py          rear 后轮模式切换
├── cmd_reset.py         reset 系统复位
├── cmd_print.py         print 调试打印
├── query_pos.py         ?pos 位置查询
└── query_lock.py        ?lock 锁定状态查询
```

**每个命令模块约定**：
```python
# services/commands/cmd_new.py
from services.command_router import router   # 导入单例路由器

@router.command("new_key")                   # 装饰器自动完成注册
def handle(ctx, value: float) -> None:
    """中文文档字符串。"""
    if ctx.command_lock:
        return
    ctx.last_cmd["new_key"] = value
```

**注意事项**：
- 包初始化时 `_autodiscover()` 自动扫描目录，导入所有 `cmd_*` / `query_*` 文件，**不需要修改 `__init__.py`**
- `command_router.router` 是模块级单例，所有装饰器注册到同一实例
- `TransportCar` 通过 `import services.commands`（触发自动发现）后直接使用单例路由器

**命令路由模式**：
- `command_router.router` 是模块级单例（在 `command_router.py` 中定义）
- 每个命令文件 `from services.command_router import router`，用 `@router.command(...)` 直接注册
- `services/commands/__init__.py` 的 `_autodiscover()` 自动扫描并导入 `cmd_*` / `query_*` 文件，触发装饰器
- `transport_car.py` 通过 `import services.commands` 触发发现，然后使用单例路由器

**原则**：
- 服务层是硬件层和控制层的粘合剂
- 负责初始化、协调和生命周期管理
- `transport_car.py` 只保留协调逻辑（控制循环、finalize、unlock），不含具体命令实现
- 每个命令模块职责单一，可独立阅读和修改

## 5. Storage Layer (`storage/`)
**职责**：处理参数的持久化

**模块**：
- `param_manager.py`：参数加载和保存

**原则**：
- 封装所有文件系统操作
- 提供统一的参数管理接口
- 处理文件不存在等边界情况

## 6. Config Layer (`config/`)
**职责**：集中管理所有可调参数

**模块**：
- `params.py`：全局参数定义

**原则**：
- 所有魔法数字都应该定义为常量
- 参数按功能分组，有清晰的注释
- 物理量包含单位说明
- 调试参数和生产参数分离

## 7. Utility Layer (`utils/`)
**职责**：提供通用工具函数

**模块**：
- `quaternion.py`：四元数数学库

**原则**：
- 工具函数应该是无状态的纯函数
- 不依赖项目特定的业务逻辑
- 可以被任何其他层使用
- 充分测试和文档化

# Coupling Rules

## Allowed Dependencies
```
services/ → control/, filters/, hardware/, storage/, config/, utils/
control/  → filters/, config/, utils/
filters/  → config/, utils/
hardware/ → config/, utils/
storage/  → config/, utils/
```

## Forbidden Dependencies
- 下层不能依赖上层（例如 `hardware/` 不能导入 `services/`）
- 同层之间尽量减少依赖
- 避免循环依赖

# Code Organization Checklist
- 新功能是否放在正确的层？
- 是否引入了不必要的层间耦合？
- 模块职责是否单一清晰？
- 是否可以独立测试？
- 是否可以方便替换实现？
- 配置是否集中管理？
- 错误处理是否在正确的层？

# Refactoring Patterns

## When to Extract
- 函数超过 50 行：考虑拆分
- 模块超过 300 行：考虑拆分
- 重复代码出现 3 次以上：提取为函数
- 职责不单一：拆分为多个模块

## How to Extract
1. 识别职责边界
2. 定义清晰的接口
3. 向下移动通用逻辑（往 utils 或 control）
4. 向上移动编排逻辑（往 services）
5. 保持硬件层最薄

# Anti-Patterns to Avoid
- 上帝类（God Class）：一个类做太多事情
- 跨层调用：跳过中间层直接调用底层
- 循环依赖：两个模块互相导入
- 全局状态：使用全局变量共享状态
- 硬编码：配置值写在代码中
- 大函数：单个函数超过 100 行

# Deliverables
- 符合分层架构的代码组织
- 清晰的模块职责说明
- 依赖关系图（如有需要）
- 重构前后的对比说明
