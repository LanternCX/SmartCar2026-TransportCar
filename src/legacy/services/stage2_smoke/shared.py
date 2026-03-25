"""Stage 2 smoke 共享 helper."""


class CaptureUart:
    """收集查询回包的简易串口对象."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


def probe_queries(tokens, probe_func, capture):
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
