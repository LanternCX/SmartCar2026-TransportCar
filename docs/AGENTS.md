# docs 索引

## 阅读顺序

1. 先读 `README.md` 判断任务是否需要文档背景。
2. 需要代码外约束时, 读 `docs/developer/` 中对应主题。
3. 需要背景、事故、调试结论或设计取舍时, 读 Serena memory。
4. 当前行为事实直接读代码、注释和行为测试。

## 主题入口

- 项目方向和路线边界: `docs/developer/strategy.md`
- 电控与运行外部约定: `docs/developer/control.md`
- 蚂蚁搬家场地坐标与边线校准图: `docs/developer/field_coordinate_calibration.svg`
- 串口链路设计约束: `docs/developer/protocol.md`
- 状态机所有权: `docs/developer/state.md`
- 视觉仓库与车端职责边界: `docs/developer/vision.md`
- 赛题资料入口: `docs/problem_statement/README.md`
- 外部参考资料归档: `docs/reference/`
- 长期协作记忆: Serena memory

## 维护规则

- 文档不镜像代码事实、接口清单、字段表、状态表或测试路径。
- 代码、注释和行为测试优先作为当前行为事实来源。
- 局部设计原因优先写在贴近代码的注释里。
- 阶段性设计取舍、调试结论和外部约束写入 Serena memory。
- 长期协作记忆只进入 Serena memory。
