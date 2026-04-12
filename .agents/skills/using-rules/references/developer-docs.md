# developer 文档入口

## 作用

- 本页用于提醒 Agent: `docs/developer/` 是当前仓库最重要的用户主文档目录之一
- 当任务涉及项目方向、任务优先级、控制主线、视觉口径或 Legacy 清理边界时, 必须优先查看这里的文档, 不要只停留在实现层规则页
- 当前正式基线采用单一 `src/`; 3.0 入口适配属于下一轮主题

## 必看原则

- 新会话或方向对齐任务, 默认先看 `docs/developer/strategy.md` 与 `docs/developer/tasks.md`
- 若任务涉及控制链、底盘闭环、运动模式、调参与诊断顺序, 继续看 `docs/developer/control.md`
- 若任务涉及视觉输入、双摄口径、字段语义、视觉主线边界, 继续看 `docs/developer/vision.md`; 但若它与当前正式基线或当前动作分工冲突, 以 `strategy.md`、`tasks.md`、`control.md` 为准
- 若任务涉及 Legacy 裁剪历史、兼容边界或回退风险, 再继续看 `docs/developer/legacy-pruning-checklist.md` 与 `docs/developer/legacy-stability-baseline.md`, 不要反向用这些历史材料覆盖当前正式基线
- 若文档提到验证要求, 当前正式口径统一为“本地自动测试 + 对话协作中的板端确认记录”

## 当前目录文件

- `strategy.md`: 项目总体方向与当前阶段主线
- `tasks.md`: 完赛路线任务拆解与阶段目标
- `control.md`: 控制链、调参与控制边界
- `vision.md`: 视觉链路与视觉协议相关方向文档, 不直接定义当前正式运行结构
- `legacy-pruning-checklist.md`: Legacy 裁剪时的检查清单
- `legacy-stability-baseline.md`: Legacy 稳定性基线与不能轻易破坏的边界

## 使用要求

- 若 `docs/developer/` 与实现层规则页存在冲突, 先判断是否已被更新 spec 显式覆盖
- 若没有被更新 spec 覆盖, 优先以 `docs/developer/` 中的主文档口径对齐
- 若文档同时提到多个目录结构, 当前正式现状统一按单一 `src/` 理解
- 不要把 `docs/developer/` 当成可选背景材料; 只要任务依赖项目方向或主线边界, 就应该先读对应文档
