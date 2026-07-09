# Core

- 项目: RT1021 搬运车模控制仓库, 目标是主辅双车协同搬运并稳定完赛, 提速服从稳定完赛。
- 主要源码边界: `src/core/` 共享底盘执行内核; `src/vision/master/` 主车角色; `src/vision/assistant/` 辅车角色; `src/protocol/` 固定短帧通信; `src/config/` 参数; `src/play/` 可编排动作流程; `src/script/` 运行和板端测试脚本。
- 正式文档入口: `README.md` 与 `docs/developer/`。文档只维护方向、外部约定和代码难以表达的设计边界; 行为事实以代码、注释和行为测试为准。
- 仓库外部依赖边界: OpenART 视觉仓库在 `../SmartCar2026-Vision`; 手柄控制上位机在 `../SmartCar2026-Controller`; 非必要不读取。
- 默认记忆入口: 先读本 memory, 再按任务读取 `mem:conventions`, `mem:runtime/core`, `mem:runtime/memory_optimization`, `mem:protocol/core`, `mem:vision/core`, `mem:hardware/core`, `mem:memory_policy`。
- 默认只读取 Serena memory; 项目演化信息由 Serena memory 承接。
