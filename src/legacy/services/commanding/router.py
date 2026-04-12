"""命令路由器, 使用显式 handler 上下文分发命令与查询."""

CommandValue = object


def tokenize(cmd_str: str):
    """将聚合命令拆分为标准化键值对序列."""
    normalized = cmd_str.strip()
    if not normalized:
        return []

    if normalized.lower() == "reset":
        return [("reset", "1")]

    tokens = []
    for part in normalized.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        tokens.append((key.strip().lower(), value.strip()))
    return tokens


class QueryResponseUART:
    """查询响应串口协议, 仅要求提供 write 接口."""

    def write(self, text: str) -> None:
        """写入一段响应文本."""


class CommandRouter:
    """注册并分发命令与查询处理器."""

    def __init__(self) -> None:
        self._cmd_handlers = {}
        self._query_handlers = {}

    def command(self, *keys: str, value_type: str = "float"):
        """注册命令处理器."""

        def decorator(func):
            for key in keys:
                self._cmd_handlers[key.strip().lower()] = {
                    "handler": func,
                    "value_type": value_type,
                }
            return func

        return decorator

    def query(self, *keys: str):
        """注册查询处理器."""

        def decorator(func):
            for key in keys:
                self._query_handlers[key.strip().lower()] = func
            return func

        return decorator

    def registered_query_tokens(self):
        """返回当前已注册的查询 token 集合."""
        return tuple(sorted(self._query_handlers))

    def route(self, line: str, ctx) -> bool:
        """解析并分发一行聚合命令."""
        normalized_line = line.strip()
        if not normalized_line:
            return False

        if normalized_line.lower() == "reset":
            command_meta = self._cmd_handlers.get("reset")
            if command_meta is None:
                return False
            command_meta["handler"](ctx, True)
            finalize = getattr(ctx, "finalize_route", None)
            if finalize is not None:
                finalize({"reset"})
            return True

        dispatched = set()
        for key, val_str in tokenize(normalized_line):
            command_meta = self._cmd_handlers.get(key)
            if command_meta is None:
                continue
            handler = command_meta["handler"]
            try:
                if command_meta.get("value_type", "float") == "raw":
                    handler(ctx, val_str)
                else:
                    handler(ctx, float(val_str))
            except ValueError:
                continue
            dispatched.add(key)

        if dispatched:
            finalize = getattr(ctx, "finalize_route", None)
            if finalize is not None:
                finalize(dispatched)
        return bool(dispatched)

    def handle_query(self, token: str, ctx) -> bool:
        """处理单条查询命令."""
        normalized = token.strip().lower()
        handler = self._query_handlers.get(normalized)
        if handler is not None:
            handler(ctx)
            return True
        ctx.reply("?unknown=%s\r\n" % normalized)
        return False


router = CommandRouter()
