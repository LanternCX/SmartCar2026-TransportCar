"""视觉控制量与坐标转换辅助."""

import math


class VisionResolvedTarget:
    """由相对控制意图换算得到的绝对目标."""

    def __init__(self, x: float, y: float, angle_deg: float, rear_only_mode: bool):
        """保存本周期绝对位置与角度目标."""
        self.x = float(x)
        self.y = float(y)
        self.angle_deg = float(angle_deg)
        self.rear_only_mode = bool(rear_only_mode)


class VisionObstacleSummary:
    """汇总当前障碍相机批次的最小摘要."""

    def __init__(self, count: int, camera_id=None, frame_id=None):
        """保存障碍数量与批次来源."""
        self.count = int(count)
        self.camera_id = None if camera_id is None else str(camera_id)
        self.frame_id = None if frame_id is None else str(frame_id)


class VisionSelectedInput:
    """状态机前置选择层输出的角色化输入."""

    def __init__(self, observation, target_role=None, obstacle_summary=None):
        """保存当前被选中的目标与障碍摘要."""
        self.observation = observation
        self.target_role = None if target_role is None else str(target_role)
        self.obstacle_summary = obstacle_summary


def _iter_detections(camera_frames, camera_ids):
    """按给定物理相机顺序展开检测列表."""
    items = []
    for camera_id in camera_ids:
        frame = camera_frames.get(str(camera_id))
        if frame is None:
            continue
        items.extend(list(getattr(frame, "detections", ())))
    return items


def _pick_best_detection(camera_frames, camera_ids, target_role: str):
    """按相机优先级和框得分挑选指定角色目标."""
    for camera_id in camera_ids:
        frame = camera_frames.get(str(camera_id))
        if frame is None:
            continue
        best = _select_detection_by_role(getattr(frame, "detections", ()), target_role)
        if best is not None:
            return best
    return None


def _resolve_camera_order(camera_frames, role_camera_priorities, target_role: str):
    """解析某个角色对应的物理相机优先级."""
    role = str(target_role)
    ordered = []
    priorities = ()
    if role_camera_priorities is not None:
        priorities = role_camera_priorities.get(role, ())
    for camera_id in priorities:
        normalized = str(camera_id)
        if normalized in camera_frames and normalized not in ordered:
            ordered.append(normalized)
    for camera_id in camera_frames:
        normalized = str(camera_id)
        if normalized not in ordered:
            ordered.append(normalized)
    return ordered


def normalize_angle(angle_deg: float) -> float:
    """将角度规范到 (-180, 180] 区间."""
    while angle_deg > 180.0:
        angle_deg -= 360.0
    while angle_deg <= -180.0:
        angle_deg += 360.0
    return angle_deg


def _score_detection(observation) -> tuple:
    """按接近程度与覆盖面积为检测框打分."""
    return (
        float(getattr(observation, "bottom", 0.0)),
        float(getattr(observation, "width", 0.0))
        * float(getattr(observation, "height", 0.0)),
        float(getattr(observation, "center_x", 0.0)),
    )


def _select_detection_by_role(detections, target_role: str):
    """从同批检测中挑选指定角色的主目标."""
    role = str(target_role)
    matches = [item for item in detections if getattr(item, "category", None) == role]
    if not matches:
        return None
    return max(matches, key=_score_detection)


def select_state_machine_input(
    cargo_frame=None,
    obstacle_frame=None,
    active_target_role=None,
    preferred_role=None,
    camera_frames=None,
    role_camera_priorities=None,
):
    """从多检测批次中挑选本拍状态机输入."""
    if preferred_role is not None and active_target_role is None:
        active_target_role = preferred_role

    frames_by_camera = {}
    if camera_frames is not None:
        for camera_id, frame in camera_frames.items():
            frames_by_camera[str(camera_id)] = frame
    else:
        if cargo_frame is not None:
            frames_by_camera[str(getattr(cargo_frame, "camera_id", "cam_a"))] = (
                cargo_frame
            )
        if obstacle_frame is not None:
            frames_by_camera[str(getattr(obstacle_frame, "camera_id", "cam_b"))] = (
                obstacle_frame
            )

    if active_target_role in ("follower", "cargo"):
        selected_role = str(active_target_role)
        selected_observation = _pick_best_detection(
            frames_by_camera,
            _resolve_camera_order(
                frames_by_camera, role_camera_priorities, selected_role
            ),
            selected_role,
        )
    else:
        selected_role = None
        selected_observation = _pick_best_detection(
            frames_by_camera,
            _resolve_camera_order(frames_by_camera, role_camera_priorities, "follower"),
            "follower",
        )
        if selected_observation is not None:
            selected_role = "follower"
        else:
            selected_observation = _pick_best_detection(
                frames_by_camera,
                _resolve_camera_order(
                    frames_by_camera, role_camera_priorities, "cargo"
                ),
                "cargo",
            )
            if selected_observation is not None:
                selected_role = "cargo"

    obstacle_summary = None
    obstacle_camera_ids = _resolve_camera_order(
        frames_by_camera, role_camera_priorities, "obstacle"
    )
    obstacle_detections = []
    for camera_id in obstacle_camera_ids:
        frame = frames_by_camera.get(camera_id)
        if frame is None:
            continue
        obstacle_detections.extend(
            [
                item
                for item in getattr(frame, "detections", ())
                if getattr(item, "category", None) == "obstacle"
            ]
        )
    if obstacle_detections:
        summary_camera_id = getattr(obstacle_detections[0], "camera_id", None)
        summary_frame_id = getattr(obstacle_detections[0], "frame_id", None)
        obstacle_summary = VisionObstacleSummary(
            count=len(obstacle_detections),
            camera_id=summary_camera_id,
            frame_id=summary_frame_id,
        )

    return VisionSelectedInput(
        observation=selected_observation,
        target_role=selected_role,
        obstacle_summary=obstacle_summary,
    )


def resolve_relative_intent(intent, odom_x: float, odom_y: float, heading_deg: float):
    """将相对控制意图转换为本周期绝对目标."""
    if not intent.active:
        return None

    theta_rad = math.radians(heading_deg)
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)
    target_x = odom_x + intent.dx_body * cos_t - intent.dy_body * sin_t
    target_y = odom_y + intent.dx_body * sin_t + intent.dy_body * cos_t
    target_angle = normalize_angle(heading_deg + intent.d_angle_deg)
    return VisionResolvedTarget(target_x, target_y, target_angle, intent.rear_only_mode)
