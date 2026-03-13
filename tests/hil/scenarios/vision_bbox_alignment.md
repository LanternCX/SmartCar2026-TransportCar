# 视觉完整框对正 HIL 场景

## 前置条件

- 设备已刷入当前代码
- OpenArt 端已切换为发送 `left,top,right,bottom`
- `uart6` 连接视觉链路, `uart3` 可用于人工查询
- 场地允许低速安全联调
- 若本轮经用户明确批准跳过 Stage 3, 本场景可不执行, 但必须在对应 HIL 记录中标记 `SKIPPED` 并说明未验证的视觉/并发风险

## 场景 A: 框中心驱动横向对正

1. 让目标框中心明显偏离画面中心
2. 持续发送完整框,例如 `left=120,top=30,right=180,bottom=200`
3. 通过 `?vision` 观察 `obs_center_x` 与 `state`
4. 观察车辆先执行横向 / 角度修正

预期行为:

- `?vision` 可看到完整框与中心信息
- 状态先进入 `ALIGN_ANGLE`
- 框中心进入死区后再切到 `ALIGN_DIST`

## 场景 B: 框底边驱动纵向对正

1. 保持目标框中心基本对中
2. 让目标框底边明显高于画面底边
3. 持续发送完整框,例如 `left=145,top=40,right=175,bottom=180`
4. 通过 `?vision` 观察 `obs_bottom`
5. 观察车辆沿纵向修正,直到框底边接近目标底边

预期行为:

- 车辆不会只依据框中心 `y` 做纵向判断
- 纵向修正依据是 `obs_bottom`
- `obs_bottom` 进入死区后,状态可进入 `ALIGN_DX`

## 场景 C: 旧 `x,y` 不再驱动视觉状态机

1. 在 `uart6` 人工发送旧格式 `x=120,y=80`
2. 紧接着查询 `?vision`
3. 再发送一帧合法完整框
4. 再次查询 `?vision`

预期行为:

- 第 1 步不会让视觉状态机获得有效观测
- 第 2 步中观测字段保持 `none` 或旧缓存状态,不会把 `x,y` 当成新观测
- 第 3 步后才出现新的完整框观测

## 证据记录

- Date:
- Firmware commit:
- Operator:
- Steps run:
- Expected:
- Actual UART output:
- Result: PASS / FAIL
- Notes:
