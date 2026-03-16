# Progress Log

## Entry Template

```markdown
# YYYY-MM-DD-N

## Date
YYYY-MM-DD

## Title
[Short actionable title]

## Background / Issue
[Context, trigger, constraints]

## Actions / Outcome
- Approach 1: [what was tried] -> [result]
- Approach 2: [what was tried] -> [result]
- Final approach: [adopted approach] -> [why it worked]

## Lessons / Refinements
- [Reusable pattern]
- [Avoidance note]

## Related Commit Message
type(scope): summary

## Related Commit Hash
TBD
```

## Global TOC

| Page ID | Date | Title | Path | Keywords |
| --- | --- | --- | --- | --- |
| 2026-03-07-1 | 2026-03-07 | 视觉状态机迁移到主控端 | `.progress/entries/2026/2026-03-07-1.md` | vision, uart6, state-machine, transport-car |
| 2026-03-07-2 | 2026-03-07 | 建立 Stage 3 设备观测诊断链路 | `.progress/entries/2026/2026-03-07-2.md` | diagnostics, mpy-cli, hil, observe, transport-car |
| 2026-03-08-1 | 2026-03-08 | 重构设备阶段为 stage2 smoke 与 stage3 人工调试 | `.progress/entries/2026/2026-03-08-1.md` | stage2, stage3, uart3, mpy-cli, diagnostics |
| 2026-03-08-2 | 2026-03-08 | 为低内存板端补齐 Stage 2 full/lite 回退 | `.progress/entries/2026/2026-03-08-2.md` | stage2, lite, memory, mpy-cli, transport-car |
| 2026-03-09-1 | 2026-03-09 | 补齐 mpy-cli skill 的串口发现与路径边界语义 | `.progress/entries/2026/2026-03-09-1.md` | mpy-cli, skill, docs, serial, path-semantics |
| 2026-03-09-2 | 2026-03-09 | 将视觉对正从单点观测切换为完整识别框 | `.progress/entries/2026/2026-03-09-2.md` | vision, bbox, uart6, state-machine, diagnostics |
| 2026-03-10-1 | 2026-03-10 | 建立工业级全局日志系统并拆分到 diagnostics 包 | `.progress/entries/2026/2026-03-10-1.md` | diagnostics, logging, uart3, transport-car, protocol |
| 2026-03-11-1 | 2026-03-11 | 修复 ORBITING 切出后的残留旋转与航向跨圈语义 | `.progress/entries/2026/2026-03-11-1.md` | vision, orbiting, rear-only, heading, transport-car |
| 2026-03-13-1 | 2026-03-13 | 解耦 transport runtime 并收紧设备验证表述 | `.progress/entries/2026/2026-03-13-1.md` | transport-runtime, commanding, diagnostics, stage2, hil |
| 2026-03-13-2 | 2026-03-13 | 修复 remote_control 启动脚本对旧 wheel_states 接口的依赖 | `.progress/entries/2026/2026-03-13-2.md` | remote-control, boot, ticker, transport-car, regression |
| 2026-03-14-1 | 2026-03-14 | 推进双摄单状态机到目标选择与 HIL 留证模板 | `.progress/entries/2026/2026-03-14-1.md` | dual-camera, state-machine, vision, hil, transport-car |
| 2026-03-15-1 | 2026-03-15 | 记录 src 运行时代码低内存重构与板级排障结论 | `.progress/entries/2026/2026-03-15-1.md` | oom, memory, runtime, logger, vision, owner, board, hardware, firmware, staged-init, handlers |
| 2026-03-15-2 | 2026-03-15 | 确认板端仍在运行旧版错误日志路径并阻塞 deploy | `.progress/entries/2026/2026-03-15-2.md` | oom, deploy, board, repl, remote-control, transport-car, logger |
| 2026-03-16-1 | 2026-03-16 | 完成搬运车最小内存占用重构设计与实施计划 | `.progress/entries/2026/2026-03-16-1.md` | memory-budget, transport-car, architecture, review, standards, plan |
| 2026-03-16-2 | 2026-03-16 | 抽出 MinimalDiagnostics 并改为按 owner 组装诊断视图 | `.progress/entries/2026/2026-03-16-2.md` | diagnostics, memory, owner, transport-car, runtime-core, queries |
| 2026-03-16-3 | 2026-03-16 | 抽出命令、运动和视觉 owner 并固化内存评审门禁 | `.progress/entries/2026/2026-03-16-3.md` | command-runtime, motion-runtime, vision-runtime, memory-review, transport-car |
| 2026-03-16-4 | 2026-03-16 | 完成主机侧全量验证并确认板端串口离线阻塞最终验收 | `.progress/entries/2026/2026-03-16-4.md` | verification, stage2, hil, serial, mpy-cli, blocked |
| 2026-03-16-5 | 2026-03-16 | 批准 src 运行时代码 300 行硬门禁并重写拆分设计 | `.progress/entries/2026/2026-03-16-5.md` | file-size, transport-car, diagnostics, vision, runtime, plan |
| 2026-03-16-6 | 2026-03-16 | 将搬运车运行时重构为 services.car 分包并补齐轻量静态契约 | `.progress/entries/2026/2026-03-16-6.md` | services.car, package-layout, pyright, pylance, mixin, memory |
| 2026-03-16-7 | 2026-03-16 | 将视觉协议与视觉状态机从共同前缀平铺文件迁移为真正分包 | `.progress/entries/2026/2026-03-16-7.md` | vision, protocol, state-machine, package, layout, doxygen |
| 2026-03-16-8 | 2026-03-16 | 继续拆分 diagnostics facade 并收紧只读 owner 聚合边界 | `.progress/entries/2026/2026-03-16-8.md` | diagnostics, facade, owner, runtime, query, file-size |
| 2026-03-16-9 | 2026-03-16 | 修复 services.car.vision 对 types 模块的板端兼容问题 | `.progress/entries/2026/2026-03-16-9.md` | micropython, types, vision, lazy-load, board, compatibility |
