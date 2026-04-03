"""@brief 日志发射与 OOM 降级逻辑.

负责格式化调用, sink 分发和 OOM 回退, 不持有运行时状态.
"""

from config.params import LOG_INFO
from diagnostics.manager.config import level_name_from_value, module_allowed


def emit_record(manager, level: int, module_name: str, message: str) -> None:
    """@brief 发射一条日志记录."""
    if level < manager.level:
        return
    if not module_allowed(manager.filter_mode, manager.filter_modules, module_name):
        return
    try:
        text = _format_log_record(level, module_name, message, manager.color_enabled)
    except MemoryError:
        report_oom(manager, "format")
        if level <= LOG_INFO:
            return
        text = build_format_oom_fallback(level)
    write_to_sinks(manager, level, text)


def report_oom(manager, stage: str) -> None:
    """@brief 上报一次 OOM 阶段标记."""
    callback = manager._oom_callback
    if callback is None:
        return
    try:
        callback(str(stage))
    except Exception:
        return


def write_to_sinks(manager, level: int, text: str) -> None:
    """@brief 向各 sink 写出已格式化文本."""
    for sink in manager.sinks:
        write_record = getattr(sink, "write_record", None)
        try:
            if write_record is not None:
                write_record(level, text)
            else:
                sink.write(text)
        except MemoryError:
            report_oom(manager, "sink")
            continue


def build_format_oom_fallback(level: int) -> str:
    """@brief 构造格式化失败时的最小降级日志文本."""
    level_name = level_name_from_value(level)
    prefix = "?"
    if level_name is not None:
        prefix = level_name[:1]
    return "%s [log.oom       ] format oom\r\n" % prefix


def _format_log_record(
    level: int,
    module_name: str,
    message: str,
    color_enabled: bool,
) -> str:
    """@brief 通过公开入口获取当前格式化函数.

    @note 这里走公开入口是为了保留测试中的 monkeypatch 兼容性
    """
    import diagnostics.manager as manager_module

    return manager_module.format_log_record(level, module_name, message, color_enabled)
