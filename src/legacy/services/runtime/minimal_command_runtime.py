"""最小命令运行时 owner."""

MINIMAL_QUERY_TOKENS = ("health", "tick", "vision")


class MinimalCommandRuntime:
    """持有最小 query 与完整命令装配策略."""

    def __init__(
        self,
        import_runtime_module,
        drop_stale_handler_modules,
        query_handlers_ready=False,
        command_handlers_ready=False,
    ) -> None:
        self._import_runtime_module = import_runtime_module
        self._drop_stale_handler_modules = drop_stale_handler_modules
        self._query_handlers_ready = bool(query_handlers_ready)
        self._command_handlers_ready = bool(command_handlers_ready)

    def registered_query_tokens(self):
        """返回最小保活 query token 视图."""
        return MINIMAL_QUERY_TOKENS

    def ensure_query_handlers(self) -> None:
        """按需装配 query handlers."""
        if self._query_handlers_ready:
            return
        handlers_module = self._import_runtime_module("services.commanding.handlers")
        start_index = getattr(handlers_module, "QUERY_HANDLER_START_INDEX", 0)
        self._drop_stale_handler_modules(start_index)
        handlers_module.load_query_handlers()
        self._query_handlers_ready = True

    def activate_full_commands(self) -> None:
        """按需装配完整命令 handlers."""
        if self._command_handlers_ready:
            return
        handlers_module = self._import_runtime_module("services.commanding.handlers")
        stop_index = getattr(handlers_module, "QUERY_HANDLER_START_INDEX", 0)
        self._drop_stale_handler_modules(0, stop_index=stop_index)
        handlers_module.load_command_handlers()
        self._command_handlers_ready = True

    @property
    def query_handlers_ready(self):
        """返回 query handlers 是否已装配."""
        return self._query_handlers_ready

    @property
    def command_handlers_ready(self):
        """返回 command handlers 是否已装配."""
        return self._command_handlers_ready
