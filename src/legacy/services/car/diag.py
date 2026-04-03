"""@brief 搬运车诊断 facade mixin.

@note
该模块只负责把多个 owner 收口成统一诊断视图, 不缓存第二份运行时状态
"""


class DiagnosticsMixin:
    """@brief 提供运行时诊断 facade 入口."""

    def get_diagnostics_facade(self):
        """@brief 返回最小诊断 facade.

        @return `MinimalDiagnostics`

        @note
        facade 首次访问时才构建, 避免在导入期和核心初始化期增加额外常驻对象
        """
        facade = getattr(self, "_diagnostics_facade", None)
        if facade is None:
            from services.runtime.minimal_diagnostics import MinimalDiagnostics

            # `runtime_core` 缺失时回退到宿主自身, 兼容 host 测试通过 `__new__` 构造的最小实例
            core_owner = getattr(self, "runtime_core", None) or self
            facade = MinimalDiagnostics(
                core=core_owner,
                command_owner=self,
                motion_owner=self,
                vision_owner=self,
            )
            self._diagnostics_facade = facade
        return facade
