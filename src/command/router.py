"""命令路由器:装饰器注册模式,将聚合命令字符串分发到独立处理器."""


class CommandRouter:
    """
    命令路由器,支持用装饰器将每条元命令注册到对应处理函数.

    用法示例::

        router = CommandRouter()

        @router.command("vx")
        def cmd_vx(ctx, value):
            ctx.last_cmd["vx"] = value

        # 处理一行聚合命令(如 "vx=10,vy=5")
        router.route("vx=10,vy=5", car)

    处理器签名统一为 ``handler(ctx, value)``,其中 ``ctx`` 为调用方传入的
    上下文对象(通常是 TransportCar 实例),``value`` 为解析后的 float 或
    str(对 print 指令).

    对于需要跨 key 后处理的指令(如 dx+dy→世界坐标变换),路由完成后会调用
    ``ctx._finalize_route(dispatched_keys)``,由上下文对象自行处理.
    """

    def __init__(self):
        """初始化处理器注册表."""
        self._cmd_handlers = {}
        self._query_handlers = {}

    # ------------------------------------------------------------------
    # 装饰器工厂
    # ------------------------------------------------------------------

    def command(self, *keys):
        """
        装饰器工厂:将被装饰函数注册为指定 key 的命令处理器.

        参数:
            keys: 一个或多个命令键(如 "vx"、"omega"、"w").
        返回:
            装饰器函数,原函数不变.
        """

        def decorator(func):
            """注册单个处理器到所有指定的命令键.

            参数:
                func: 处理函数.

            返回:
                原处理函数,保持不变.
            """
            for key in keys:
                self._cmd_handlers[key] = func
            return func

        return decorator

    def query(self, *keys):
        """
        装饰器工厂:将被装饰函数注册为指定 token 的查询处理器.

        查询处理器签名为 ``handler(ctx)``,不接收 value 参数.

        参数:
            keys: 一个或多个查询 token(如 "pos"、"lock").
         返回:
            装饰器函数,原函数不变.
        """

        def decorator(func):
            """注册单个查询处理器到所有指定的查询键.

            参数:
                func: 查询处理函数.

            返回:
                原处理函数,保持不变.
            """
            for key in keys:
                self._query_handlers[key] = func
            return func

        return decorator

    # ------------------------------------------------------------------
    # 路由执行
    # ------------------------------------------------------------------

    def route(self, line, ctx):
        """
        解析一行聚合命令字符串,将每条元命令分发到对应处理器.

        解析规则:
        - 按逗号分割得到各元命令
        - 每条元命令必须含 ``=``,格式为 ``key=value``
        - key 统一转为小写
        - "print" 命令的 value 保留为字符串;其余 value 转为 float
        - 无法解析的元命令静默跳过

        参数:
            line: 原始命令行字符串,如 ``"vx=10,vy=5,dx=0.3"``.
            ctx:  上下文对象(TransportCar),handlers 以其为第一参数.
        返回:
            True 表示至少分发了一条命令;False 表示未识别到任何处理器.
        副作用:
            路由结束后调用 ``ctx._finalize_route(dispatched_keys)``(若方法存在).
        """
        line = line.strip()
        if not line:
            return False

        # 特殊处理裸 "reset" 指令(无等号)
        if line == "reset":
            handler = self._cmd_handlers.get("reset")
            if handler:
                handler(ctx, True)
                dispatched = {"reset"}
                if hasattr(ctx, "_finalize_route"):
                    ctx._finalize_route(dispatched)
                return True
            return False

        dispatched = set()
        parts = line.split(",")

        for part in parts:
            if "=" not in part:
                continue
            key, val_str = part.split("=", 1)
            key = key.strip().lower()
            val_str = val_str.strip()

            handler = self._cmd_handlers.get(key)
            if handler is None:
                continue

            # "print" 保留字符串,其余转 float
            if key == "print":
                handler(ctx, val_str)
            else:
                try:
                    handler(ctx, float(val_str))
                except ValueError:
                    continue

            dispatched.add(key)

        if dispatched and hasattr(ctx, "_finalize_route"):
            ctx._finalize_route(dispatched)

        return bool(dispatched)

    def handle_query(self, token, ctx, source="uart3"):
        """
        处理一条查询指令(去掉 "?" 前缀后的 token).

        参数:
            token: 查询关键字,如 ``"pos"``、``"lock"``.
            ctx:   上下文对象(TransportCar).
            source: 查询来源串口名,用于选择响应回写口.
        返回:
            True 表示找到并调用了对应处理器;False 表示未知查询.
        """
        token = token.strip().lower()
        handler = self._query_handlers.get(token)
        response_uart = getattr(ctx, source, None)
        if response_uart is None and hasattr(ctx, "uart3"):
            response_uart = ctx.uart3
        if handler:
            had_uart = hasattr(ctx, "_query_response_uart")
            previous_uart = getattr(ctx, "_query_response_uart", None)
            had_source = hasattr(ctx, "_query_source")
            previous_source = getattr(ctx, "_query_source", None)
            try:
                setattr(ctx, "_query_response_uart", response_uart)
                setattr(ctx, "_query_source", source)
                handler(ctx)
                return True
            finally:
                if had_uart:
                    setattr(ctx, "_query_response_uart", previous_uart)
                elif hasattr(ctx, "_query_response_uart"):
                    delattr(ctx, "_query_response_uart")
                if had_source:
                    setattr(ctx, "_query_source", previous_source)
                elif hasattr(ctx, "_query_source"):
                    delattr(ctx, "_query_source")
        # 未知查询:回写 unknown 响应
        if response_uart is not None:
            response_uart.write("?unknown=%s\r\n" % token)
        return False


# 模块级单例路由器:命令模块通过 @router.command() 直接注册到此实例
router = CommandRouter()
