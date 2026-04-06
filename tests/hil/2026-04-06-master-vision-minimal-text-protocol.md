# 2026-04-06 主车与视觉最小文本协议联调 HIL 留证

## 状态

- 当前状态: 待执行
- 自动化状态: 已完成
- HIL 状态: 待人工
- 留证范围: 主车最小文本视觉输入、视觉端最小文本输出、主车到辅车跟随报文

## 自动化留证

- 主车仓库: `pytest tests/unit/master/test_app.py tests/unit/master/test_decision.py tests/unit/master/test_runtime_loop.py tests/unit/master/test_runtime_params.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_parser.py tests/contract/test_openart_protocol_doc_contract.py`
- 主车结果: `88 passed`
- 视觉仓库: `pytest tests/unit/test_vision_protocol_rebuild.py tests/contract/test_main_vision_protocol_contract.py`
- 视觉结果: `25 passed`

## 本轮 HIL 目标

- 验证视觉端启动阶段可选一次 `reset=1` 后进入持续回传主线
- 验证视觉端有目标时输出 `v=1,s=<seq>,x=<x>,y=<y>`
- 验证视觉端无目标时输出 `v=0,s=<seq>`
- 验证主车可稳定消费来自视觉端的最小文本报文
- 验证主车对有效目标输出 `follow=1,seq=...,valid=1,dx=...,dy=...`
- 验证主车对无目标或超时场景输出 `follow=1,seq=...,valid=0,dx=0.000,dy=0.000`

## 待执行步骤

1. 记录本次主车仓库版本、视觉仓库版本、设备连接方式与串口信息。
2. 烧录并启动视觉端，确认是否启用启动阶段单次 `reset=1`。
3. 在串口侧留证视觉端启动输出。
4. 构造有目标场景，记录视觉端连续输出与主车接收表现。
5. 构造无目标场景，记录视觉端连续输出与主车接收表现。
6. 记录主车输出的 `follow=1,...` 跟随报文。
7. 若存在异常，补充异常现象、复现条件与暂定结论。

## 待填结果

- 主车版本:
- 视觉版本:
- 视觉端口:
- 主车端口:
- 是否发送启动 `reset=1`:
- 视觉端启动输出原始样例:
- 有目标视觉输出:
- 无目标视觉输出:
- 主车接收观察:
- 主车 `valid=1` 跟随输出样例/结果:
- 主车 `valid=0` 跟随输出样例/结果:
- `UART6` 连续不少于 200 帧逐行完整:
- `UART6` 留档位置:
- `UART8` 连续不少于 200 帧逐行完整:
- `UART8` 留档位置:
- 主车连续观察 200 拍时, 因解析失败导致的无效拍次数:
- 同一观察窗口内, 是否出现连续 3 拍及以上格式错误无效帧:
- `UART3` 输出跳变次数:
- `UART3` 对比样本位置:
- `UART3` 前后对比结论:
- 人工结论:

## 结论

- hil_pending
