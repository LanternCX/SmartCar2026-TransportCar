# Play 延迟导入与回库阶段内存经验

2026-07-07 运行时内存优化 Task 1 中，包入口聚合导入被移除，角色运行时不再在 import 阶段无条件加载 play runner/context/routine。

板端日志显示，若 `MasterReturnGaragePlay` 延迟到 `RETURN_GARAGE_RETREAT` 阶段首次导入，会在低余量阶段触发较大的首次分配，出现 `memory allocation failed`，随后模块半初始化导致 `can't import name MasterReturnGaragePlay`。

当前策略：

- `protocol/__init__.py` 和 `play/__init__.py` 保持轻入口，不做聚合导入。
- 主车和辅车运行时都在启动 play 首次加载时创建 `PlayRunner` / `PlayContext` 并缓存启动 play 类。
- 同一时机预热并缓存各自的回库 play 类，回库入口不执行首次导入。
- 主车缓存 `MasterReturnGaragePlay`，辅车缓存 `AssistantReturnGaragePlay`；角色差异只保留在具体 routine 和状态迁移语义上。

原则：延迟导入用于降低 import 阶段常驻集合，但不能把必经冷路径首次分配推到更低内存余量的比赛后段。必经阶段的大块首次分配应放在已验证可承受的初始化后早期阶段，并用板端内存点确认。