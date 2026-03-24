# refactor Index

## Type
refactor

## Global TOC

| Page ID | Date | Title | Path | Related Change Unit | Keywords |
| --- | --- | --- | --- | --- | --- |
| 2026-03-24-1 | 2026-03-24 | 将 skill 私有正文迁入对应 skill 并补齐 reference-sync 维护边界 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-24-1.md` | 把 `mpy-cli`、OpenArt 协议和 `reference-sync` 的职责重新收口为 Skill 持有正式正文、维护信息独立登记的稳定结构，并补齐 git-workflow 的提交尾注禁令。 | skills, reference-sync, mpy-cli, openart, git-workflow, docs |
| 2026-03-08-1 | 2026-03-08 | 重构设备阶段为 stage2 smoke 与 stage3 人工调试 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-08-1.md` | 重构设备验证阶段边界，将自动化 smoke 收束到 Stage 2，并把 Stage 3 明确定义为 uart3 人工调试流程。 | stage2, stage3, uart3, mpy-cli, diagnostics |
| 2026-03-10-1 | 2026-03-10 | 建立工业级全局日志系统并拆分到 diagnostics 包 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-10-1.md` | 建立统一日志系统并把日志核心从服务编排层收口到 diagnostics 包边界。 | diagnostics, logging, uart3, transport-car, protocol |
| 2026-03-13-1 | 2026-03-13 | 解耦 transport runtime 并收紧设备验证表述 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-13-1.md` | 解耦 transport runtime 管线，删除兼容壳，并收紧设备验证结论与证据表述。 | transport-runtime, commanding, diagnostics, stage2, hil |
| 2026-03-15-1 | 2026-03-15 | 记录 src 运行时代码低内存重构与板级排障结论 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-15-1.md` | 围绕板端 OOM 对 src 运行时代码进行低内存重构，并沉淀板级排障结论。 | oom, memory, runtime, logger, vision, owner, board, hardware, firmware, staged-init, handlers |
| 2026-03-16-1 | 2026-03-16 | 抽出 MinimalDiagnostics 并改为按 owner 组装诊断视图 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-16-1.md` | 抽出 MinimalDiagnostics，并把诊断查询改为按 owner 只读组装。 | diagnostics, memory, owner, transport-car, runtime-core, queries |
| 2026-03-16-2 | 2026-03-16 | 抽出命令、运动和视觉 owner 并固化内存评审门禁 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-16-2.md` | 继续抽出命令、运动和视觉 owner，并把内存评审门禁正式固化到规范与文档。 | command-runtime, motion-runtime, vision-runtime, memory-review, transport-car |
| 2026-03-16-3 | 2026-03-16 | 将搬运车运行时重构为 `services.car` 分包并补齐轻量静态契约 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-16-3.md` | 将搬运车运行时从平铺文件迁到 services.car 真正分包，并补齐轻量静态契约。 | services.car, package-layout, pyright, pylance, mixin, memory |
| 2026-03-16-4 | 2026-03-16 | 将视觉协议与视觉状态机从共同前缀平铺文件迁移为真正分包 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-16-4.md` | 将视觉协议和状态机从共同前缀平铺模块迁移为真正分包，并同步更新布局约束。 | vision, protocol, state-machine, package, layout, doxygen |
| 2026-03-16-5 | 2026-03-16 | 继续拆分 diagnostics facade 并收紧只读 owner 聚合边界 | `docs/superpowers/memory/refactor/entries/2026-03/2026-03-16-5.md` | 继续拆分 diagnostics facade 内部职责，并保持只读 owner 聚合边界。 | diagnostics, facade, owner, runtime, query, file-size |
