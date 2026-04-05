# TransportCar 启动期内存打点设计

## 背景

当前板端通过 `boot.py -> script/remote_control.py -> TransportCar(...)` 的正常启动链后, 在 `load_gyro_offsets()` 的日志格式化阶段出现 `MemoryError`。从调用栈看, 直接崩点位于 `diagnostics.format.sanitize_log_text()` 的字符串清洗分配路径, 但还需要板端证据确认初始化各阶段的内存变化。

## 目标

在不依赖现有 logger 的前提下, 为 `TransportCar` 启动流程加入最小侵入的原始内存打点, 让板端可以直接观察关键初始化节点的 `mem_free` 与 `mem_alloc` 变化, 以便确认问题发生前的内存收缩位置。

## 方案

采用原始 `uart3.write()` 输出, 避开 `LogManager -> format_log_record -> sanitize_log_text()` 路径, 防止调试代码本身再次触发可疑的字符串格式化分配。打点输出统一使用简短单行文本:

`MEM <label> free=<n> alloc=<n>`

关键节点放在:

1. UART 初始化后
2. IMU 初始化后
3. 电机/编码器初始化后
4. 辨识参数加载后
5. `load_gyro_offsets()` 前
6. `load_gyro_offsets()` 后

## 约束

- 不改变现有控制逻辑与错误处理语义
- 不通过 logger 输出调试信息
- 若宿主环境没有 `gc.mem_free()` / `gc.mem_alloc()`, 主机单测路径应安全退化
- 本次仅为定位问题增加证据, 不直接优化日志系统

## 验证

- 先通过单元测试锁定探针输出行为与顺序
- 再由用户上传到板端, 通过真实启动链观察输出
