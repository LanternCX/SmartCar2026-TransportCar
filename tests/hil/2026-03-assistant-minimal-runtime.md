# 2026-03 辅车最小运行时 HIL 留证

## 1. 操作步骤

1. 连接目标设备串口
2. 记录当前测试版本
3. 执行 `python3 tools/run_stage2_smoke.py --port <port>`
4. 记录 smoke 输出中的连接、导入和最小查询结果
5. 人工发送 `follow=1,seq=1,valid=1,dx=0.050,dy=0.100,d_angle=0.000`
6. 记录状态回传 `state=1,...`
7. 暂停控制输入直到超过超时窗口, 观察 `timeout=1`

## 2. 预期行为

- 设备可连接
- 辅车运行时可导入
- `PING` / `STATE?` 等最小协议可响应
- `follow=1,...` 跟随报文可被解析
- 状态回传符合 `state=1,follow_active=...,last_seq=...,odom_x=...,odom_y=...,heading=...,timeout=...`

## 3. 实测输出

- 版本:
- 端口:
- stage2 命令:
- 关键输出:
- 人工观察:
- 主机侧验证: `python3 -m pytest tests/unit tests/contract -q` -> `32 passed`

## 4. 结论

- `hil_pending`
