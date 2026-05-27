# docs 索引

## 阅读顺序

1. 先读 `README.md` 判断任务属于哪个代码区域。
2. 再读 `docs/developer/` 中对应主题的短索引。
3. 按短索引进入具体代码、注释和测试。
4. 需要理解背景、事故或设计取舍时，再查 `docs/superpowers/memory/`。

## 主题入口

- 项目方向和路线边界: `docs/developer/strategy.md`
- 电控与运行入口: `docs/developer/control.md`
- 串口链路与协议入口: `docs/developer/protocol.md`
- 状态机所有权: `docs/developer/state.md`
- 视觉仓库与车端职责边界: `docs/developer/vision.md`
- 赛题资料: `docs/problem_statement/README.md`
- 可复用协作结论: `docs/superpowers/memory/`

## 维护规则

- 文档通过索引渐进式披露代码，不镜像代码事实。
- 代码、注释和行为测试优先作为事实来源。
- 局部设计原因优先写在贴近代码的注释里，阶段性设计取舍优先写入 memory。
- 文档没有行为测试同等保护，不承担代码功能说明的事实源职责。
- `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 根目录只放尚未归属到已合并 PR 的新文档；归档文件按 `archive/PR#<id>/` 存放。
