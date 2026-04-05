# legacy 裁剪清单

## 1. 目的

- 本清单用于冻结 `src/legacy` 后续裁剪顺序
- 本清单只定义哪些内容必须迁移, 哪些内容只保留在 `legacy`, 哪些内容可在新系统稳定后归档
- 任何删减都必须先对照 `docs/superpowers/specs/archive/PR#16/2026-03-24-master-assistant-minimal-runtime-design.md`
- `src/legacy` 只作为参考, 不再要求保持旧入口可运行
- 旧仓库对应测试在归档后整体退出当前主线验证面

## 2. 必须迁移到新系统的内容

### 2.1 稳定性内核

- 底盘控制语义
- 滤波链语义
- 运动学语义
- 陀螺仪解算语义
- 四元数 / 欧拉角转换语义
- 关键方向 / 符号约定
- 关键参数语义

对应旧系统范围:

- `src/legacy/control/`
- `src/legacy/filters/`
- `src/legacy/utils/quaternion.py`
- `src/legacy/services/runtime/motion_runtime.py`

### 2.2 主车最小能力

- 单视觉串口轮询双摄拓扑
- 简化视觉状态机
- 目标选择
- 主车自身运动目标输出
- 对辅车的最小运动级命令构造

对应旧系统范围:

- `src/legacy/vision/`
- `src/legacy/services/car/vision.py`
- `src/legacy/services/runtime/vision_runtime_service.py`
- `src/legacy/services/commanding/handlers/query_vision.py`

### 2.3 辅车最小能力

- `ARM / DISARM / STOP / PING / STATE?`
- `VEL / MOVE / HOLD / RESET_ODOM`
- 最小执行状态
- 超时停机与急停保护
- 最小 `STATE` 回包

对应旧系统范围:

- `src/legacy/services/runtime/uart_ingress.py`
- `src/legacy/services/runtime/runtime_core.py`
- `src/legacy/services/commanding/router.py`
- `src/legacy/services/commanding/context.py`

### 2.4 基础入口参考

以下内容保留为启动参考, 但当前不列为第一版硬迁移项:

- 旧按钮入口切换语义
- 旧启动顺序与初始化流程语义

对应旧系统范围:

- `src/legacy/boot.py`

### 2.5 后续阶段能力参考

以下内容保留在 `legacy` 中作为后续阶段能力参考, 但当前不列为第一版最小系统硬迁移项:

- 灰度传感器边界检测与越线判定语义

对应旧系统范围:

- 若后续在 `src/legacy/` 中确认存在独立灰度实现文件, 则以该具体路径为准
- 在明确具体路径前, 灰度相关内容只作为策略参考, 不进入第一版删减判断

## 3. 只保留在 `legacy` 的内容

以下内容在当前阶段只保留在 `src/legacy`, 不进入新系统:

- 统一 `vehicle_role` 分流运行时
- 旧 `services.car` facade 与兼容桥接
- 复杂 lazy mixin 装配
- 自动发现式 handler / query 装配
- 旧 diagnostics 聚合面
- 旧 transport/runtime 兼容层
- 旧视觉外围查询面和调试面
- 旧主辅共用角色分流入口
- 旧仓库对应测试

若同一项同时命中“必须迁移”和“只保留在 legacy”, 优先按以下顺序判断:

1. 先保留其稳定性 / 完赛语义
2. 再允许重写其新系统实现
3. 原旧实现本体继续保留在 `legacy`

## 4. 新系统稳定后可归档的旧内容

当以下 3 个条件同时满足时, 才允许把对应旧内容从“常看参考”降级为“归档参考”:

1. `master` 主机侧验证通过, 且 `tests/hil/2026-03-master-minimal-runtime.md` 填入实测结果并给出 PASS / FAIL 结论
2. `assistant` 主机侧验证通过, 且 `tests/hil/2026-03-assistant-minimal-runtime.md` 填入实测结果并给出 PASS / FAIL 结论
3. 主辅最小运动级协议已完成联调留证, 且 `tests/hil/2026-03-master-assistant-protocol.md` 填入实测结果并给出 PASS / FAIL 结论

其中“主机侧验证通过”固定指以下命令全部通过, 且不允许以相似测试、子集测试或人工口头说明替代:

- `master`: `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py -q`
- `assistant`: `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_protocol.py tests/unit/assistant/test_safety.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_app.py -q`
- 主辅协议: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py -q`

满足后可考虑归档的旧内容:

- 旧 `services/runtime/` 装配路径
- 旧 `services/commanding/` 自动注册路径
- 旧 `vision/` 复杂查询与扩展调试路径
- 旧 `diagnostics/` 非核心查询与输出路径

## 5. 明确禁止直接删除的内容

在没有替代实现和验证证据前, 禁止删除:

- `legacy` 中与底盘控制、滤波、运动学、姿态解算直接相关的实现
- `legacy` 中用于解释方向 / 符号 / 参数语义的关键实现
- `legacy` 中用于对照双摄轮询行为的关键协议实现
- `legacy` 中与按钮入口和启动顺序有关的关键实现
- 若后续确认存在明确灰度实现路径, 则该路径对应内容在阶段 B 前不得直接删除

## 6. 删除顺序冻结

后续删减顺序固定如下:

1. 先完成 `assistant` 最小系统验证
2. 再完成 `master` 最小系统验证
3. 再完成主辅协议联调验证
4. 再标记哪些旧结构只保留参考用途
5. 最后才决定是否进一步裁剪 `legacy` 中的非关键外围

## 7. 审核口径

每次计划删除旧内容前, 必须回答:

- 这项内容是否已经在 `master` 或 `assistant` 中有稳定替代
- 删除后是否会影响完赛主线
- 删除后是否还保留足够的稳定性参考基线

并必须记录到以下载体之一:

- `tests/hil/2026-03-master-minimal-runtime.md`
- `tests/hil/2026-03-assistant-minimal-runtime.md`
- `tests/hil/2026-03-master-assistant-protocol.md`

主机侧验证命令与结果也统一记录到上述 3 份留证文档中, 不再使用额外分散载体。

只要其中任一答案不明确, 该删除项就不能进入执行。
