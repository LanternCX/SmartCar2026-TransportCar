# 2026-03 主辅跟随协议 HIL 留证

## 状态

- 当前状态: 待执行
- 原因: 当前已完成主机侧验证, 但用户暂时离开, 尚未提供板端联调时机

## 目标

- 验证主车能正确下发 `follow=1,...` 高频跟随报文
- 验证辅车能正确解析 `seq/valid/dx/dy/d_angle` 字段
- 验证辅车最小状态回传与当前专项协议一致

## 预期步骤

1. 启动主车与辅车最小运行时
2. 由主车发送 `follow=1,seq=1,valid=1,dx=...,dy=...,d_angle=...`
3. 再发送 `follow=1,seq=2,valid=0,dx=0.000,dy=0.000,d_angle=0.000`
4. 观察辅车状态回传 `state=1,follow_active=...,last_seq=...,odom_x=...,odom_y=...,heading=...,timeout=...`
5. 断开或暂停控制输入直到超过超时窗口
6. 记录失败归因与主机侧契约版本

## 预期结果

- `follow=1,...` 文本格式稳定
- 辅车能正确解析数值字段并按 `seq` 丢弃旧包
- `valid=0` 能让辅车进入保持策略
- 超过超时窗口后 `timeout=1`
- `state=1,...` 至少包含 `follow_active` / `last_seq` / `odom_x` / `odom_y` / `heading` / `timeout`

## 实测输出

- 版本:
- 主车发送:
- 辅车回包:
- 协议对齐判断:
- 失败归因:
- 主机侧验证: `python3 -m pytest tests/unit tests/contract -q` -> `32 passed`

## 结论

- hil_pending
