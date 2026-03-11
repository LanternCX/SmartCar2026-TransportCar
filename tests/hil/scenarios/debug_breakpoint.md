# debug 断点 HIL 场景

## 前置条件

- 设备已刷入当前代码
- `uart3` 已连接人工调试串口
- 若需要运动中断点, 场地具备安全刹停条件

## 场景 A: `debug()` 等待与释放

1. 在板端可执行路径中插入一次 `debug()` 调用并重新部署
2. 运行程序, 让流程走到该断点
3. 观察 `uart3` 输出 `DEBUG wait: send debug=1 on uart3 to resume.`
4. 在 `uart3` 发送 `debug=1`
5. 观察 `uart3` 输出 `DEBUG resume.`
6. 恢复后立刻查询 `?tick` 或观察下一拍姿态 / 里程计输出

预期行为:

- 到达断点后主流程暂停
- 仅 `uart3` 的 `debug=1` 可释放等待
- 释放后程序从断点后继续执行
- 恢复后的首个控制周期无异常大 `dt` 跳变

## 场景 B: 等待期间电机输出安全

1. 让车辆先进入低速运动或保持非零占空比状态
2. 触发 `debug()`
3. 观察车辆动作与 `?motor` / 示波器 / 电调现象

预期行为:

- 进入等待后电机占空比立即清零
- 车辆不继续保持进入断点前的旧输出
- 恢复后首拍输出平滑, 无明显突兀冲击

## 场景 C: `uart6` 不释放断点

1. 让程序停在 `debug()`
2. 保持 `uart3` 不发送释放指令
3. 仅从 `uart6` 发送 `debug=1`
4. 再从 `uart6` 发送一条普通控制命令, 例如 `vx=1`
5. 最后从 `uart3` 发送 `debug=1`

预期行为:

- 程序继续保持等待
- 不因 `uart6` 的 `debug=1` 恢复执行
- 恢复后不会执行等待期间发到 `uart6` 的旧控制命令

## 证据记录

- Date:
- Firmware commit:
- Operator:
- Steps run:
- Expected:
- Actual UART output:
- Resume tick evidence:
- Result: PASS / FAIL
- Notes:
