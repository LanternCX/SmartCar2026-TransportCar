"""辅车角色运行时诊断快照

@file src/vision/assistant/diagnostics.py
"""


def build_follow_snapshot(
    control_snapshot: dict,
    control_status: str,
    vision_snapshot: dict,
    vision_status: str,
    last_error_text: str,
    fusion: object = None,
) -> dict:
    """组织辅车角色层最小诊断快照

    @brief 按需生成对外观测字段, 避免控制周期每拍构造完整字典
    """

    if fusion is None:
        # 角色层尚未生成融合结果时, 诊断默认返回静止输出
        state = "idle"
        control_contribution = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        vision_contribution = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        fusion_output = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    else:
        state = getattr(fusion, "state")
        control_contribution = dict(getattr(fusion, "control_contribution"))
        vision_contribution = dict(getattr(fusion, "vision_contribution"))
        fusion_output = {
            "vx": float(getattr(fusion, "vx")),
            "vy": float(getattr(fusion, "vy")),
            "omega": float(getattr(fusion, "omega")),
        }

    # 诊断只导出联调所需字段, 不暴露角色层内部运行状态对象
    return {
        "state": state,
        "control_age_ms": control_snapshot.get("age_ms"),
        "vision_age_ms": vision_snapshot.get("age_ms"),
        "control_input": control_snapshot,
        "control_input_status": control_status,
        "vision_input": vision_snapshot,
        "vision_input_status": vision_status,
        "last_error_text": last_error_text,
        "control_contribution": control_contribution,
        "vision_contribution": vision_contribution,
        "fusion_output": fusion_output,
    }
