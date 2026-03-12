"""Stage 2 full 模式 helper."""


class CaptureUart:
    """收集查询回包的简易串口对象."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


def _probe_queries(tokens, probe_func, capture):
    """执行一组查询探针并返回查询结果摘要."""
    query_outputs = {}
    query_ok = 1
    for name in tokens:
        before_count = len(capture.messages)
        probe_func(name)
        text = (
            capture.messages[-1].strip() if len(capture.messages) > before_count else ""
        )
        if text:
            query_outputs[name] = text
        if not text.startswith("?%s=" % name):
            query_ok = 0
    return query_ok, query_outputs


def collect_full_transport_summary(tokens):
    """执行 full 模式下的完整安全 smoke."""
    from services.commanding.router import router
    from services.transport_car import TransportCar

    car = TransportCar(diagnostic_mode=True)
    registered = router.registered_query_tokens()
    missing = [name for name in tokens if name not in registered]

    car.pit_flag = True
    step_ok = 1 if car.step() else 0
    facade = car.get_diagnostics_facade()
    snapshots = {
        "health": facade.build_health_snapshot(),
        "tick": facade.build_tick_snapshot(),
        "imu": facade.build_imu_snapshot(),
        "enc": facade.build_encoder_snapshot(),
        "motor": facade.build_motor_snapshot(),
        "vision": facade.build_vision_snapshot(),
    }

    capture = CaptureUart()
    setattr(car, "uart3", capture)
    query_ok, query_outputs = _probe_queries(
        tokens, lambda name: car.handle_uart_line("?%s" % name, source="uart3"), capture
    )

    status = "ok"
    reason = "ok"
    if missing:
        status = "fail"
        reason = "missing queries: %s" % ";".join(missing)
    elif not query_ok:
        status = "fail"
        reason = "query chain failed"
    elif not step_ok:
        status = "fail"
        reason = "step returned false"
    elif int(car.tick_count) <= 0:
        status = "fail"
        reason = "tick did not advance"

    return {
        "status": status,
        "reason": reason,
        "transport_mode": "full",
        "init_ok": 1,
        "query_count": len(registered),
        "missing_queries": missing,
        "query_ok": query_ok,
        "query_outputs": query_outputs,
        "step_ok": step_ok,
        "tick_count": int(car.tick_count),
        "snapshots": snapshots,
    }
