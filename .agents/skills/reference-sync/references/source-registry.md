# 文档来源登记

## 使用说明

- 本页只登记来源、正式落点和同步触发条件，不承接正式正文。
- 若某份正式正文已迁入对应 Skill，后续在这里维护来源与落点，不在 `reference-sync` 再放第二份正文。
- 更新正式正文时，必须同步复核本页与 `maintenance-checklist.md`。

## 来源登记表

| 文档名称 | 外部或历史来源 | 当前正式落点 | 更新时机或同步触发条件 |
| --- | --- | --- | --- |
| `mpy-cli` 正式文档 | 已删除的根 `docs/` 旧 mpy-cli 正文；上游工具文档与仓库内实际命令行为 | `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` | `mpy-cli` 命令、参数、路径约定、无交互流程或排障结论变化时 |
| OpenArt 协议正文 | 已删除的根 `docs/` 旧 OpenArt 协议正文；设备通信协议原始约定与仓库内已确认实现 | `.agents/skills/using-rules/references/openart-protocol.md` | 协议字段、链路约定、兼容说明、示例报文或硬件连接约束变化时 |
| `problem_statement` 题面使用说明 | 本地维护对象：`docs/problem_statement/README.md` | `docs/problem_statement/README.md` | 题面文档结构、阅读顺序、维护方式或目录组织调整时 |
| `problem_statement` 来源与追溯 | 本地维护对象：`docs/problem_statement/sources.md` | `docs/problem_statement/sources.md` | 官方题面来源、抓取链路、本地产物映射或清洗依据变化时 |
| `problem_statement` 规格正文 | 本地维护对象：`docs/problem_statement/spec.md` | `docs/problem_statement/spec.md` | 官方规则正文更新、REQ 编号调整或需要补充规则事实时 |
| `problem_statement` 问答正文 | 本地维护对象：`docs/problem_statement/qa.md` | `docs/problem_statement/qa.md` | 官方问答新增、规则澄清变化或现有解释失效时 |
