# 绕行继承目标跟踪状态 bug

## 现象
主车在 `MASTER_DEBUG_DISPLAY_ENABLED=True` 时阈值识别正常，关闭调试显示后进入绕行阶段可能识别不到目标。

## 根因
搜索/接近阶段上报“找到目标”事件时，如果立即清空目标跟踪状态，后续绕行阶段虽然切到 blob-only 阈值跟踪，但 `track_task_name` / 动态阈值等目标记忆已经丢失，导致绕行不知道应该按哪个目标继续找。调试预览会扫全图固定阈值，因此可能掩盖这个问题。

## 约束
- 搜索/接近阶段创建事件后，不应立即清空目标跟踪记忆。
- 状态同步到非绕行任务时，可以由状态切换逻辑清理跟踪状态。
- 状态同步到绕行任务时，应保留上一阶段的目标跟踪状态。
- 辅车绕行后进入 `APPROACH_OBJECT + OBJECT + TRANSPORT` 或 `ORBIT + OBJECT + TRANSPORT` 做搬运前再对正时，也应保留目标跟踪状态；否则随后进入 `TRANSPORT_OBJECT + OBJECT + TRANSPORT` 时会失去 blob-only 阶段所需的目标记忆。
- 对应回归测试应覆盖“找到目标事件 ACK 后进入绕行，绕行仍能识别同一目标”，以及“绕行后进入搬运前再对正，再进入正式搬运，正式搬运仍能继承目标”。

## 已知保护
主车 v2 使用 `test_master_main_v2_orbit_inherits_track_after_search_event` 覆盖绕行继承链路。辅车 v2 使用 `test_assistant_main_v2_orbit_inherits_track_after_object_event` 和 `test_assistant_main_v2_transport_object_inherits_track_after_transport_realign` 覆盖绕行与搬运继承链路。