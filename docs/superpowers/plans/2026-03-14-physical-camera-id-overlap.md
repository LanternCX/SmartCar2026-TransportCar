# 物理相机 ID 与重叠类别协议改造 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将双摄协议从“职责相机 ID”改造为“物理相机 ID + 可重叠类别”, 并同步主控侧选择层与视觉端输出格式。

**Architecture:** 先改主控仓库文档和测试, 再把主控选择层从固定两路语义帧升级为多物理相机帧集合选择。随后在 `../SmartCar2026-Vision` 落地 query/response、多检测、多类别和物理 `camera_id` 透传, 最后做主机回归与设备侧联调。

**Tech Stack:** Python, pytest unit/contract tests, MicroPython/OpenMV style UART protocol, HIL docs.

---

### Task 1: 收敛主控侧协议文档到物理相机 ID 语义

**Files:**
- Modify: `.agents/skills/using-rules/references/openart-protocol.md`
- Modify: `docs/developer/strategy.md`
- Modify: `tests/hil/2026-03-dual-camera-polling.md`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

新增或修改断言, 让日志和 HIL 说明不再依赖 `obstacle/cargo` 作为 `camera_id` 口径。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: FAIL, 原因应为文档和测试夹具仍默认语义化 `camera_id`。

**Step 3: Write minimal implementation**

把协议和说明文字统一改成“`camera_id` 是物理相机, `category` 可重叠”。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS.

### Task 2: 为主控选择层增加“多物理相机 + 重叠类别”测试

**Files:**
- Modify: `tests/unit/services/test_vision_state_machine.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

新增测试, 明确以下行为:

```python
def test_select_state_machine_input_prefers_active_role_across_multiple_camera_frames():
    ...

def test_overlapping_category_from_two_cameras_uses_priority_camera_before_score_tie_break():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL, 原因应为当前实现仍把相机帧按 `cargo_frame/obstacle_frame` 固定分路。

**Step 3: Write minimal implementation**

先只补测试, 不改生产代码。

**Step 4: Run test to verify it fails correctly**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL, 且失败原因与固定语义帧假设一致。

### Task 3: 主控运行时改为按物理相机集合轮询和选择

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `src/vision/transforms.py`
- Modify: `src/vision/coordinator.py`
- Test: `tests/unit/services/test_vision_state_machine.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`
- Test: `tests/unit/services/test_uart_ingress.py`

**Step 1: Write the failing test**

使用 Task 2 的失败测试作为 RED 基线。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_uart_ingress.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

- 在 `transport_car.py` 中引入物理相机 poll 列表与优先级配置
- 在 `transforms.py` 中把输入从固定 `cargo_frame/obstacle_frame` 改成多帧集合选择
- 在 `coordinator.py` 中保留按物理 `camera_id` 缓存, 必要时提供当前有效帧集合接口

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_uart_ingress.py -q`
Expected: PASS.

### Task 4: 视觉仓库补齐物理相机 ID + 多检测协议

**Files:**
- Modify: `../SmartCar2026-Vision/main.py`
- Modify: `../SmartCar2026-Vision` 协议正文
- Modify: `../SmartCar2026-Vision/README.md`
- Test: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- Test: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**Step 1: Write the failing test**

新增测试, 锁定以下行为:

```python
def test_query_frame_returns_multiple_detections_with_physical_camera_id():
    ...

def test_unaddressed_camera_stays_silent_even_when_category_overlaps():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest ../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py ../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py -q`
Expected: FAIL, 原因应为当前视觉端仍是单相机、单目标、bbox-only 连续发送。

**Step 3: Write minimal implementation**

- 在视觉端增加物理 `camera_id` 配置
- 增加 query/response 入口
- 按一帧 `0..N` 条检测输出 `camera_id/frame_id/category/bbox`
- 追加 `frame_end=1`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest ../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py ../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py -q`
Expected: PASS.

### Task 5: 做跨仓库主机回归与联调准备

**Files:**
- Modify: `tests/hil/2026-03-dual-camera-polling.md`
- Modify: `../SmartCar2026-Vision/README.md`

**Step 1: Write the failing test**

本任务不新增 host 失败测试, 改为补齐联调步骤和 query 示例, 要求 HIL 文档不再使用职责相机 ID。

**Step 2: Run test to verify baseline**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 3: Write minimal implementation**

把 HIL / README 里的查询示例统一改成物理 `camera_id`, 并加入“类别可重叠”的联调说明。

**Step 4: Run test to verify host side still passes**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

### Task 6: Stage 2 / Stage 3 联调与 HIL 留证

**Files:**
- Modify: `tests/hil/2026-03-dual-camera-polling.md`

**Step 1: Write the failing test**

本任务不新增 host 自动化失败测试, 改为执行设备验证并填入真实输出。

**Step 2: Run Stage 2**

Run: `python3 tools/run_stage2_smoke.py --port <PORT>`
Expected: `status=ok`。

**Step 3: Run Stage 3 / HIL**

通过 `uart3` 验证:

1. `?frame=<physical_camera_id>` 查询可用
2. 未被点名相机严格静默
3. 两颗相机都可返回同类 `category`
4. 主车在重叠类别下仍稳定选择主目标

**Step 4: Record evidence**

将实际输出、结论和剩余风险写入 `tests/hil/2026-03-dual-camera-polling.md`。
