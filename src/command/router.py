"""命令路由器: 装饰器注册模式, 将聚合命令字符串分发到独立处理器"""


class CommandRouter:
    """
    @brief 命令路由器, 支持用装饰器将每条元命令注册到对应处理函数

    @details
    通过装饰器模式实现命令与处理函数的松耦合绑定.处理器接收上下文对象和解析后的值,
    便于在 TransportCar 等实体上执行具体操作.对于需要多键协作的指令(如 dx+dy 的世界坐标变换),
    路由完成后通过 _finalize_route 回调交由上下文对象统一处理, 避免路由器过度耦合业务逻辑

    用法示例: ::

        router = CommandRouter()

        @router.command("rear")
        def cmd_rear(ctx, value):
            ctx.rear_only_mode = bool(value)

        router.route("rear=1", car)

    处理器签名统一为 ``handler(ctx, value)``:
    @param ctx 调用方传入的上下文对象(通常是 TransportCar 实例)
    @param value 解析后的 float 或 str(对 print 指令)
    """

    def __init__(self):
        """
        @brief 初始化命令处理器注册表

        @note
        _cmd_handlers: 存储命令键到处理函数的映射, 键为命令字符串(如"vx"), 值为处理函数
        """
        self._cmd_handlers = {}

    def command(self, *keys):
        """
        @brief 装饰器工厂: 将被装饰函数注册为指定 key 的命令处理器

        @details
        支持一个处理器绑定多个命令键, 实现命令的聚合处理.注册后的处理器将在 route() 方法中
        根据命令键被调用, 处理 TransportCar 的状态更新

        @param keys 一个或多个命令键(如 "vx"、"omega"、"w")
        @return 装饰器函数, 原函数保持不变以支持链式装饰
        """

        def decorator(func):
            """
            @brief 将处理函数注册到所有指定的命令键

            @param func 处理函数, 接收 ctx 和 value 两个参数
            @return 原处理函数, 保持不变以支持多层装饰器叠加
            """
            for key in keys:
                self._cmd_handlers[key] = func
            return func

        return decorator

    def route(self, line, ctx):
        """
        @brief 解析一行聚合命令字符串, 将每条元命令分发到对应处理器

        @details
        解析规则设计考虑串口通信的实际情况:
        - 逗号分隔支持批量下发多个命令, 减少通信开销
        - key 统一小写避免大小写敏感导致的解析失败
        - print 命令保留字符串以支持调试信息输出
        - 无效命令静默跳过确保系统鲁棒性

        特殊处理裸 "reset" 指令: 考虑到 reset 是高频操作且无需参数, 单独处理以简化调用方代码

        @param line 原始命令行字符串, 如 ``"rear=1, dx=0.3"``
        @param ctx 上下文对象(TransportCar), handlers 以其为第一参数, 用于状态更新
        @return True 表示至少分发了一条命令; False 表示未识别到任何处理器

        @note
        路由结束后调用 ``ctx._finalize_route(dispatched_keys)``(若方法存在),
        用于处理需要多键协作的指令(如 dx+dy→世界坐标变换)
        """
        line = line.strip()
        if not line:
            return False

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


# 模块级单例路由器: 命令模块通过 @router.command() 直接注册到此实例
router = CommandRouter()
