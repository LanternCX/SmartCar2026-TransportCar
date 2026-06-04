# milestone Index

## Type
milestone

## Global TOC

| Page ID | Date | Title | Path | Related Change Unit | Keywords |
| --- | --- | --- | --- | --- | --- |
| 2026-06-03-1 | 2026-06-03 | 接入 OpenART 物体 YOLO 识别链路 | `docs/superpowers/memory/milestone/entries/2026-06/2026-06-03-1.md` | 记录 OpenART 物体识别切到 YOLO, 黄线和辅车色标保留原算法, 部署脚本按参数同步模型文件的闭环。 | openart, yolo, object-detection, master, assistant, vision, milestone |
| 2026-05-31-2 | 2026-05-31 | 收口主车回库为黄线采样停车 | `docs/superpowers/memory/milestone/entries/2026-05/2026-05-31-2.md` | 记录主车回库取消色标状态, 以 Y=160 有黄色且 X=270 连续 5 帧无黄色完成停车收口回库主线。 | return-garage, yellow-line, fixed-sample, master, vision, state-machine, milestone |
| 2026-05-30-1 | 2026-05-30 | 完成全部物体后黄线与色标回库闭环 | `docs/superpowers/memory/milestone/entries/2026-05/2026-05-30-1.md` | 记录车端和 OpenART 主车视觉共同完成全部物体后后退对正黄线、黄线左移、绿色色标跟随、完成同步辅车停止的回库闭环。 | return-garage, yellow-line, green-marker, master, assistant, vision, state-machine, milestone |
| 2026-05-25-1 | 2026-05-25 | 接入主辅绕行阶段视觉平移修正 | `docs/superpowers/memory/milestone/entries/2026-05/2026-05-25-1.md` | 记录主车和辅车绕行阶段通过 OpenART 输出 `v,<vx>,<vy>` 平移修正, 并在车端统一绕行基准运动上叠加修正量。 | orbit, vision, uart6, master, assistant, correction, milestone |
| 2026-05-08-2 | 2026-05-08 | 完成主辅车联动搬运状态闭环 | `docs/superpowers/memory/milestone/entries/2026-05/2026-05-08-2.md` | 记录 PR#64、PR#68、PR#70、PR#76 和 PR#80 将主车和辅车状态机串成搜索、绕行、对正、搬运、收尾和下一轮搜索的完整协同搬运闭环。 | PR64, PR68, PR70, PR76, PR80, state-machine, master, assistant, transport, milestone |
| 2026-05-08-1 | 2026-05-08 | 确立 UDP 数据流与 TCP 可靠同步双模式控制协议 | `docs/superpowers/memory/milestone/entries/2026-05/2026-05-08-1.md` | 记录 PR#60 和 PR#61 将控制协议收口为高频 UDP 数据流与低频 TCP 可靠同步的短包通信基线。 | PR60, PR61, protocol, UDP, TCP, reliable-sync, high-frequency, short-packet, milestone |
| 2026-04-30-1 | 2026-04-30 | 完成 PR#61 短包通信协议与状态机前置边界收口 | `docs/superpowers/memory/milestone/entries/2026-04/2026-04-30-1.md` | 记录 PR#61 将短包通信协议、车端运行时入口、主辅车链路、视觉链路、Mono Repo 边界、测试和归档统一收口为状态机前置基线。 | PR61, protocol, short-packet, runtime, vision, mono-repo, state-machine, milestone |
| 2026-04-16-2 | 2026-04-16 | 切换主辅正式通信链路到 UART8 | `docs/superpowers/memory/milestone/entries/2026-04/2026-04-16-2.md` | 把当前阶段主辅正式通信链路整体从 `UART3` 切到 `UART8`，同步收口运行时代码、测试、开发文档和规则入口。 | master, assistant, uart8, uart6, runtime, protocol, docs, milestone |
| 2026-04-16-1 | 2026-04-16 | 完成主车与辅车双侧角色运行时开发闭环 | `docs/superpowers/memory/milestone/entries/2026-04/2026-04-16-1.md` | 记录辅车跟随运行时与主车 UART3 速度转发运行时先后落地后，主辅双侧角色运行时开发收口为统一里程碑。 | master, assistant, uart3, uart6, runtime, follow, forward, milestone |
| 2026-04-14-1 | 2026-04-14 | 重写双车协同搬运路线的正式开发文档口径 | `docs/superpowers/memory/milestone/entries/2026-04/2026-04-14-1.md` | 重写 strategy、tasks、control 和 vision 四份正式开发文档，使其统一表达新的双车协同搬运路线、关键能力和演进顺序。 | docs, strategy, tasks, control, vision, dual-car, state-machine, feedforward, milestone |
| 2026-04-12-1 | 2026-04-12 | 完成当前视觉协议生效文档与代码事实的基线收口 | `docs/superpowers/memory/milestone/entries/2026-04/2026-04-12-1.md` | 记录当前视觉协议生效文档、归档边界与文档契约测试统一收口到代码事实基线的完整里程碑。 | vision, docs, protocol, archive, uart6, milestone |
| 2026-04-04-1 | 2026-04-04 | 完成主车底盘控制重构阶段的姿态、方向与节拍闭环调试 | `docs/superpowers/memory/milestone/entries/2026-04/2026-04-04-1.md` | 记录主车底盘控制重构阶段完成姿态口径统一、方向映射修正、动态 dt 统一和航向保持语义收口的完整里程碑。 | master, chassis-control, heading, yaw, mapping, dynamic-dt, milestone |
| 2026-03-07-1 | 2026-03-07 | 视觉状态机迁移到主控端 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-07-1.md` | 将视觉状态机职责迁入主控端搬运车运行时，形成主控内部视觉闭环与位置式控制协同。 | vision, uart6, state-machine, transport-car |
| 2026-03-07-2 | 2026-03-07 | 建立 Stage 3 设备观测诊断链路 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-07-2.md` | 建立可由 agent 主动触发的 Stage 3 板端观测诊断链路，并补齐运行时诊断快照与设备观测入口。 | diagnostics, mpy-cli, hil, observe, transport-car |
| 2026-03-09-1 | 2026-03-09 | 补齐 mpy-cli skill 的串口发现与路径边界语义 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-09-1.md` | 补齐 mpy-cli skill 对串口发现、上传路径边界和运维命令语义的指导，收口 agent 默认操作顺序。 | mpy-cli, skill, docs, serial, path-semantics |
| 2026-03-14-1 | 2026-03-14 | 推进双摄单状态机到目标选择与 HIL 留证模板 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-14-1.md` | 推进双摄单状态机方案到目标选择、批次处理和 HIL 留证模板阶段。 | dual-camera, state-machine, vision, hil, transport-car |
| 2026-03-16-1 | 2026-03-16 | 完成搬运车最小内存占用重构设计与实施计划 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-1.md` | 完成搬运车最小内存占用重构的正式设计与实施计划，并把内存门禁提升为评审硬约束。 | memory-budget, transport-car, architecture, review, standards, plan |
| 2026-03-16-2 | 2026-03-16 | 完成主机侧全量验证并确认板端串口离线阻塞最终验收 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-2.md` | 完成主机侧全量验证，并把板端最终验收明确标记为受串口离线阻塞。 | verification, stage2, hil, serial, mpy-cli, blocked |
| 2026-03-16-3 | 2026-03-16 | 批准 src 运行时代码 300 行硬门禁并重写拆分设计 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-3.md` | 批准 src 运行时代码 300 行硬门禁，并重写后续拆分设计。 | file-size, transport-car, diagnostics, vision, runtime, plan |
| 2026-03-26-1 | 2026-03-26 | 重定向 OpenArt 辅车跟随主线到位置式高频闭环 | `docs/superpowers/memory/milestone/entries/2026-03/2026-03-26-1.md` | 将当前阶段目标收敛为 OpenArt 误差驱动的主车高频位置式控制与辅车持续闭环响应。 | follow-control, openart, position-control, imu, memory |
