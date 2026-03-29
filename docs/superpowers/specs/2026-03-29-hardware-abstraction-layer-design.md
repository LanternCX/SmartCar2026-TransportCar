# 硬件抽象层设计文档

**项目**: SmartCar2026-TransportCar  
**日期**: 2026-03-29  
**版本**: 1.0  

## 1. 设计目标

为主车（Master）和辅车（Assistant）系统实现硬件抽象层，使其能够通过 mpy cli 工具直接烧录到 RT1021 板运行，并保证：

- **内存碎片化控制**：系统启动时一次性分配所有硬件对象内存，避免运行时动态内存分配
- **低内存开销**：优化硬件对象设计，减少不必要的内存占用
- **稳定性保障**：确保硬件稳定性控制链路（速度环、串环、四元数积分、欧拉角转换、位置环）的完整性和可靠性
- **代码可维护性**：提供清晰的硬件抽象接口，便于后续维护和扩展

## 2. 设计原则

### 2.1 内存管理原则
- **预分配策略**：所有硬件对象在系统初始化时一次性创建并分配内存
- **静态生命周期**：硬件对象在整个系统运行期间保持存在，不进行释放和重新分配
- **集中管理**：通过硬件管理器统一管理所有硬件对象，避免分散内存分配

### 2.2 架构设计原则
- **单一职责**：每个硬件模块负责特定类型的硬件操作
- **抽象分离**：硬件抽象层与业务逻辑分离，降低耦合度
- **配置集中**：硬件配置参数集中定义，便于维护和修改
- **错误处理**：提供硬件操作失败的优雅降级机制

## 3. 架构设计

### 3.1 目录结构

```
src/master/board/
├── __init__.py
├── hardware.py      # 硬件管理器，集中创建和管理所有硬件对象
├── motors.py        # 电机抽象接口
├── encoders.py      # 编码器抽象接口  
├── imu.py           # IMU抽象接口
└── uart.py          # UART通信抽象接口

src/assistant/board/
├── __init__.py
├── hardware.py      # 硬件管理器
├── motors.py        # 电机抽象接口
├── encoders.py      # 编码器抽象接口
├── imu.py           # IMU抽象接口  
└── uart.py          # UART通信抽象接口
```

### 3.2 核心组件

#### 3.2.1 HardwareManager（硬件管理器）
- **职责**：负责所有硬件对象的创建、初始化和生命周期管理
- **内存策略**：在 `__init__` 方法中创建所有硬件对象，确保一次性内存分配
- **接口提供**：为其他模块提供硬件访问接口

#### 3.2.2 硬件抽象接口
- **Motors**：电机控制抽象，提供电机速度、方向控制接口
- **Encoders**：编码器抽象，提供轮速读取接口
- **IMU**：惯性测量单元抽象，提供姿态数据接口
- **UART**：串行通信抽象，提供数据收发接口

### 3.3 系统集成方式

#### 3.3.1 Master系统集成
```python
class MasterApp:
    def __init__(self, ...):
        # 创建硬件管理器
        self.hardware = HardwareManager()
        self.hardware.init_all()
        
        # 将硬件接口注入到运行时模块
        self.motion_runtime = MotionRuntime(
            hardware=self.hardware.get_stability_chain()
        )
```

#### 3.3.2 Assistant系统集成
```python
class AssistantApp:
    def __init__(self, ...):
        # 创建硬件管理器
        self.hardware = HardwareManager()
        self.hardware.init_all()
        
        # 将硬件接口注入到运行时模块
        self.runtime = MotionRuntime(
            hardware=self.hardware.get_command_chain()
        )
```

## 4. 硬件配置

### 4.1 引脚配置
沿用 legacy 目录的引脚定义，确保硬件兼容性：

**电机配置**：
- 中间电机(m): PWM_C30_DIR_C31, 13000Hz, 不反向 (invert=False)
- 左电机(l): PWM_D4_DIR_D5, 13000Hz, 不反向 (invert=False)  
- 右电机(r): PWM_D6_DIR_D7, 13000Hz, 反向 (invert=True)

**编码器配置**：
- 中间编码器(m): D15/D16, 反向计数 (invert=True)
- 左编码器(l): C0/C1, 反向计数 (invert=True)
- 右编码器(r): C2/C3, 反向计数 (invert=True)

**UART配置**：
- UART3: UART(2), 115200 bps, 数据采样和调试输出
- UART6: UART(5), 115200 bps, 命令接收和查询响应

### 4.2 方向配置一致性要求

**重要原则**：新的硬件抽象层实现必须与 legacy 目录中的方向配置保持完全一致，任何偏差都可能导致车辆运动错误。

#### 4.2.1 电机方向配置
电机方向配置必须严格遵循 legacy 实现：

```python
# 电机方向配置常量
MOTOR_DIRECTION_CONFIG = {
    "m": {"pwm": "PWM_C30_DIR_C31", "freq": 13000, "invert": False},
    "l": {"pwm": "PWM_D4_DIR_D5", "freq": 13000, "invert": False},  
    "r": {"pwm": "PWM_D6_DIR_D7", "freq": 13000, "invert": True}
}
```

**配置说明**：
- 中间电机(m): 不反向 (invert=False)
- 左电机(l): 不反向 (invert=False)  
- 右电机(r): 反向 (invert=True)

#### 4.2.2 编码器方向配置
编码器方向配置必须严格遵循 legacy 实现：

```python
# 编码器方向配置常量
ENCODER_DIRECTION_CONFIG = {
    "m": {"a_pin": "D15", "b_pin": "D16", "invert": True},
    "l": {"a_pin": "C0", "b_pin": "C1", "invert": True},
    "r": {"a_pin": "C2", "b_pin": "C3", "invert": True}
}
```

**配置说明**：
- 所有编码器都必须启用反转计数 (invert=True)
- 这是 legacy 中经过验证的正确配置，不得修改

#### 4.2.3 车体系方向约定
车体系方向约定必须与现有实现保持一致：

```python
# 车体系方向约定常量
BODY_AXIS_SEMANTICS = {
    "x_positive": "right",           # X轴正向为右
    "y_positive": "forward",         # Y轴正向为前
    "omega_positive": "clockwise",   # 角速度正向为顺时针
    "heading_positive": "clockwise"  # 航向角正向为顺时针
}
```

**约定说明**：
- 所有运动学计算必须基于此约定
- 硬件抽象层不得改变此约定
- 必须确保硬件配置与此约定匹配

#### 4.2.4 方向一致性验证
硬件管理器必须在初始化时验证方向配置的正确性：

```python
def _validate_direction_config(self):
    """验证硬件方向配置是否与 legacy 完全一致"""
    
    # 验证电机方向配置
    expected_motor_invert = {"m": False, "l": False, "r": True}
    for wheel_name, motor in self._motors.items():
        actual_invert = motor.invert
        expected_invert = expected_motor_invert[wheel_name]
        if actual_invert != expected_invert:
            raise HardwareError(
                f"电机方向配置错误: {wheel_name} 轮期望 invert={expected_invert}, 实际 invert={actual_invert}"
            )
    
    # 验证编码器方向配置  
    expected_encoder_invert = {"m": True, "l": True, "r": True}
    for wheel_name, encoder in self._encoders.items():
        actual_invert = encoder.invert
        expected_invert = expected_encoder_invert[wheel_name]
        if actual_invert != expected_invert:
            raise HardwareError(
                f"编码器方向配置错误: {wheel_name} 轮期望 invert={expected_invert}, 实际 invert={actual_invert}"
            )
```

#### 4.2.5 测试验证要求
必须编写测试用例验证方向配置的正确性：

```python
# 电机方向测试
def test_motor_directions_match_legacy():
    motors = create_motors()
    assert motors["m"].invert == False, "中间电机应该不反向"
    assert motors["l"].invert == False, "左电机应该不反向"
    assert motors["r"].invert == True, "右电机应该反向"

# 编码器方向测试  
def test_encoder_directions_match_legacy():
    encoders = create_encoders()
    assert encoders["m"].invert == True, "中间编码器应该反转计数"
    assert encoders["l"].invert == True, "左编码器应该反转计数"
    assert encoders["r"].invert == True, "右编码器应该反转计数"

# 车体系约定测试
def test_body_axis_semantics_match_legacy():
    semantics = body_axis_semantics()
    assert semantics["x_positive"] == "right"
    assert semantics["y_positive"] == "forward" 
    assert semantics["omega_positive"] == "clockwise"
    assert semantics["heading_positive"] == "clockwise"
```

### 4.3 稳定性控制链路
确保以下控制链路的完整性：
- 速度环控制
- 串环控制
- 四元数积分
- 欧拉角转换
- 位置环控制

## 5. 实现要点

### 5.1 内存优化要点
- 避免在硬件操作方法中创建临时对象
- 使用基本数据类型而非复杂对象结构
- 预先分配所有需要的缓冲区和数据结构
- 避免递归调用导致的栈内存消耗

### 5.2 实时性保障
- 硬件操作方法执行时间可预测
- 避免在关键路径上进行阻塞操作
- 提供硬件状态的快速查询接口

### 5.3 错误处理
- 硬件初始化失败时提供降级方案
- 运行时硬件错误不影响系统核心功能
- 提供硬件状态监控和恢复机制

## 6. 验证标准

### 6.1 功能验证
- 所有硬件设备能够正常初始化和操作
- 主车和辅车能够独立运行
- 稳定性控制链路功能完整
- 主辅车通信正常

### 6.2 方向一致性验证（关键验证项）
- **电机方向**：必须与 legacy 配置完全一致（m:不反向, l:不反向, r:反向）
- **编码器方向**：必须与 legacy 配置完全一致（所有编码器反转计数）
- **车体系约定**：必须与现有实现保持一致（x:右, y:前, omega:顺时针）
- **运动学一致性**：硬件配置与车体系约定必须匹配，运动方向正确

### 6.3 性能验证
- 内存碎片化控制在可接受范围内
- 系统运行期间内存使用稳定
- 实时控制响应时间满足要求

### 6.4 兼容性验证
- 能够通过 mpy cli 工具直接烧录到 RT1021 板
- 与现有硬件配置完全兼容
- 烧录后系统能够直接运行

### 6.5 测试覆盖率要求
- **单元测试**：每个硬件组件的方向配置必须通过单元测试验证
- **集成测试**：硬件抽象层与现有系统的集成必须通过测试
- **方向测试**：必须编写专门的方向一致性测试用例
- **回归测试**：修改硬件配置后必须通过完整的回归测试

## 7. 风险评估

### 7.1 技术风险
- **内存不足风险**：RT1021 内存资源有限，需严格控制内存使用
- **实时性风险**：硬件操作响应时间可能影响控制精度
- **兼容性风险**：新设计与现有硬件可能存在适配问题
- **方向配置风险**：方向配置与 legacy 不一致可能导致车辆运动错误（高风险）

### 7.2 缓解措施
- 严格内存使用预算和监控
- 关键路径性能测试和优化
- 充分的硬件兼容性测试
- **方向配置强制验证**：硬件管理器初始化时必须验证方向配置，任何偏差立即报错
- **测试覆盖**：为方向配置编写专门的测试用例，确保与 legacy 完全一致
- **文档记录**：在代码注释中明确记录方向配置的 legacy 依据，防止误修改

## 8. 后续计划

1. **硬件抽象层实现**：按照本文档实现硬件抽象层，**重点确保方向配置与 legacy 完全一致**
2. **方向配置测试**：优先编写方向配置测试用例，验证电机、编码器、车体系约定的正确性
3. **系统集成测试**：验证与现有系统的集成，确保方向一致性
4. **性能优化**：针对内存和实时性进行优化，同时保持方向配置正确
5. **硬件烧录验证**：验证通过 mpy cli 工具烧录运行，**最终验证车辆运动方向的正确性**

### 8.1 关键检查点
- **方向配置检查点**：在硬件管理器初始化时强制检查方向配置
- **测试检查点**：所有方向配置测试用例必须通过
- **集成检查点**：系统集成测试中必须包含方向一致性验证
- **烧录前检查点**：烧录前必须验证方向配置文档与代码实现的一致性

### 8.2 验收标准
硬件抽象层必须满足以下条件才能验收：
- ✅ 所有方向配置与 legacy 完全一致
- ✅ 所有方向配置测试用例通过
- ✅ 集成测试中运动方向正确
- ✅ 烧录到硬件后车辆运动方向符合预期
- ✅ 内存碎片化和性能指标满足要求

---

**设计状态**: 已通过架构设计评审  
**下一步**: 制定详细实现计划  
**关键约束**: 方向配置必须与 legacy 完全一致，这是硬件抽象层成功的必要条件