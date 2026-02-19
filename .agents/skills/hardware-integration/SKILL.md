---
name: hardware-integration
description: Guide hardware driver development, peripheral integration, and real-time system constraints.
---

# Purpose
规范硬件驱动的开发和集成流程，确保硬件接口的稳定性、实时性和可维护性。

# When to Use
- 添加新的硬件外设（传感器、执行器）
- 调试硬件通信问题
- 优化硬件接口性能
- 处理实时性约束和时序问题

# Hardware Platform

## Target MCU
- **型号**：RT1021 (NXP i.MX RT1021)
- **运行环境**：MicroPython
- **控制周期**：5ms (200Hz)
- **实时约束**：严格，不能有阻塞操作

## Peripheral Interfaces
- **UART**：串口通信（调试和控制）
- **PWM**：电机驱动（占空比控制）
- **Encoder**：编码器读取（脉冲计数）
- **IMU**：惯性测量单元（SPI/I2C）
- **Timer**：定时器中断（控制周期）

# Driver Development Guidelines

## 1. Hardware Abstraction Layer
**原则**：
- 每个硬件外设一个独立模块
- 提供统一的初始化、读写、关闭接口
- 隐藏寄存器和底层实现细节
- 错误处理和边界检查

**模板**：
```python
"""
硬件模块名称
"""
from typing import Optional

class HardwareDevice:
    """硬件设备抽象类"""
    
    def __init__(self, config: dict) -> None:
        """
        初始化硬件设备
        
        Args:
            config: 配置字典，包含引脚、参数等
        """
        self._initialized = False
        self._config = config
        # 硬件初始化
        
    def read(self) -> Optional[float]:
        """
        读取硬件数据
        
        Returns:
            读取的数据，失败返回 None
        """
        if not self._initialized:
            return None
        # 实现读取逻辑
        
    def write(self, value: float) -> bool:
        """
        写入硬件数据
        
        Args:
            value: 要写入的值
            
        Returns:
            成功返回 True，失败返回 False
        """
        if not self._initialized:
            return False
        # 实现写入逻辑
        
    def close(self) -> None:
        """关闭硬件设备，释放资源"""
        self._initialized = False
```

## 2. UART Communication
**用途**：
- UART3：调试输出（单向）
- UART6：控制命令和查询（双向）

**注意事项**：
- 发送前后加延迟避免总线冲突
- 非阻塞读取，避免等待超时
- 缓冲区管理，防止溢出
- 字符串解析要高效

**示例**：
```python
# 非阻塞读取
if uart.any():
    data = uart.read()
    # 处理数据
    
# 发送带延迟
def send_message(uart, msg: str) -> None:
    """发送消息并避免冲突"""
    time.sleep_ms(5)  # 发送前延迟
    uart.write(msg)
    time.sleep_ms(5)  # 发送后延迟
```

## 3. Motor Control (PWM)
**控制参数**：
- 频率：10kHz（典型值）
- 占空比：0-10000（`MAX_DUTY`）
- 方向：正反转引脚控制

**注意事项**：
- 占空比限幅，防止过载
- 启动时缓慢增加，避免冲击
- 停止时渐降到零
- 方向切换时先停止再反转

**示例**：
```python
def set_motor_duty(motor, duty: int) -> None:
    """
    设置电机占空比
    
    Args:
        motor: 电机对象
        duty: 占空比，正数正转，负数反转
    """
    # 限幅
    duty = max(-MAX_DUTY, min(MAX_DUTY, duty))
    
    # 设置方向
    if duty >= 0:
        motor.set_forward()
    else:
        motor.set_reverse()
        
    # 设置占空比
    motor.set_pwm(abs(duty))
```

## 4. Encoder Reading
**编码器参数**：
- 类型：霍尔编码器（磁性）
- 分辨率：7 PPR × 4 倍频 × 30 减速比 = 840 脉冲/转
- 读取方式：定时器硬件计数

**注意事项**：
- 霍尔编码器噪声大，必须滤波
- 定期清零计数器，防止溢出
- 方向判断要准确
- 速度计算要考虑控制周期

**滤波策略**：
```
原始脉冲 → 中值滤波（去尖峰）→ 双窗口回归（拟合）→ 差分限幅（防突变）
```

## 5. IMU Integration
**传感器型号**：IMU660RB（六轴）
- 陀螺仪：角速度测量
- 加速度计：仅用于静态校准，不积分位置

**初始化流程**：
1. 硬件初始化（SPI/I2C）
2. 读取设备 ID 验证通信
3. 配置量程和滤波
4. 加载陀螺仪零飘校准值

**陀螺仪使用**：
```python
# 读取原始数据
raw_gyro = imu.read_gyro()

# 零飘补偿
gyro_z = (raw_gyro[GYRO_AXIS_Z] - gyro_offset_z) / GYRO_SCALE

# 低通滤波
gyro_z_filtered = lpf.update(gyro_z)

# 四元数积分更新姿态
quat.integrate(gyro_x, gyro_y, gyro_z, dt)

# 提取航向角
yaw = quat.to_euler()[2]  # Z 轴欧拉角
```

**注意事项**：
- 陀螺仪零飘必须校准（`calibrate_gyro.py`）
- 控制周期 `dt` 要准确测量
- 四元数归一化防止累积误差
- 加速度计不能用于位置积分（误差太大）

## 6. Timer & Interrupt
**控制周期实现**：
- 使用硬件定时器（`PIT` 或 `TIM`）
- 周期：5ms（200Hz）
- 优先级：最高，不能被打断

**中断处理原则**：
```python
# 主循环标志
tick_ready = False

def timer_callback(timer) -> None:
    """定时器中断回调"""
    global tick_ready
    tick_ready = True  # 只设置标志，不做复杂操作

# 主循环
while True:
    if tick_ready:
        tick_ready = False
        # 执行控制周期任务
        car.step()
```

**注意事项**：
- 中断函数要快，复杂逻辑放主循环
- 避免中断中分配内存
- 避免中断中调用耗时函数（如串口输出）
- 全局变量访问要原子化

# Real-Time Constraints

## 5ms Control Cycle Budget
- **读取传感器**：< 1ms（编码器、IMU）
- **滤波计算**：< 0.5ms（多级滤波）
- **控制计算**：< 1ms（PID、运动学）
- **电机输出**：< 0.5ms（PWM 更新）
- **串口处理**：< 1ms（非阻塞）
- **余量**：> 1ms（应对抖动）

## Performance Optimization
- 减少浮点运算：关键路径用定点数
- 避免动态分配：预分配对象重用
- 减少函数调用：内联小函数
- 减少字符串操作：用整数 ID
- 批量操作：一次读写多个数据

## Timing Measurement
```python
from time import ticks_us, ticks_diff

start = ticks_us()
# 执行操作
elapsed = ticks_diff(ticks_us(), start)
print(f"耗时: {elapsed} us")
```

# Hardware Testing

## Unit Test for Each Driver
1. **初始化测试**：能否成功初始化
2. **读写测试**：读写数据是否正确
3. **边界测试**：超量程或异常输入
4. **持续测试**：长时间运行稳定性
5. **性能测试**：操作耗时是否满足要求

## Integration Test
1. **硬件连接测试**：所有外设都能通信
2. **时序测试**：控制周期稳定性
3. **负载测试**：满负载运行不丢数据
4. **干扰测试**：电机运行时传感器读数

## Debug Tools
- **串口监听**：UART3 实时输出状态
- **示波器**：PWM 波形、编码器脉冲
- **逻辑分析仪**：数字信号时序
- **万用表**：电压、电流测量

# Common Hardware Issues

## 问题 1：编码器读数跳变
**症状**：速度突然跳变很大
**原因**：霍尔编码器受电机干扰
**解决**：
- 增强滤波（中值滤波器）
- 电机加磁环减少 EMI
- 走线分离（信号线远离电源线）

## 问题 2：电机不转或反转
**症状**：给定 PWM 但电机不响应
**原因**：
- 方向引脚接反
- PWM 频率不对
- 电源不足

**解决**：
- 检查引脚配置
- 调整 PWM 频率（10-20kHz）
- 检查电源电压和电流

## 问题 3：IMU 读数异常
**症状**：陀螺仪输出全是零或很大
**原因**：
- SPI/I2C 通信失败
- 设备地址错误
- 供电不稳定

**解决**：
- 读取设备 ID 验证通信
- 检查引脚和地址配置
- 加去耦电容稳定供电

## 问题 4：串口乱码
**症状**：接收到的数据不完整
**原因**：
- 波特率不匹配
- 缓冲区溢出
- 总线冲突

**解决**：
- 统一波特率（通常 115200）
- 及时读取清空缓冲区
- 发送前后加延迟

## 问题 5：控制周期不稳定
**症状**：周期时而 5ms 时而 10ms
**原因**：
- 中断被其他任务打断
- 某个操作阻塞太久
- 中断优先级设置错误

**解决**：
- 提高定时器中断优先级
- 优化耗时操作（移出中断）
- 检查是否有死循环或等待

# File Organization
```
hardware/
├── __init__.py         # 空文件或模块初始化
├── uart_bus.py         # 串口通信
├── motors.py           # 电机驱动
├── encoders.py         # 编码器
└── imu.py              # IMU 传感器
```

# Deliverables
- 功能完整的硬件驱动模块
- 详细的中文接口文档
- 硬件连接和配置说明
- 单元测试和集成测试结果
- 性能和时序测量数据
