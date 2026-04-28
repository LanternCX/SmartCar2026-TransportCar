# 文档来源登记

## 使用说明

- 本页只登记来源、正式落点和同步触发条件，不承接正式正文。
- 正式正文由对应 Skill、开发文档或外部仓库维护；`reference-sync` 只登记来源与维护入口。
- 更新正式正文时，必须同步复核本页与 `maintenance-checklist.md`。

## 来源登记表

| 文档名称 | 来源 | 正式落点 | 更新时机或同步触发条件 |
| --- | --- | --- | --- |
| `mpy-cli` 正式文档 | `@../mpy-cli-dev` 仓库中的 `README.md`、`docs/developer-guide.md`、`mpy_cli/` 与 `tests/` | `@../mpy-cli-dev` | `mpy-cli` 命令、参数、路径约定、无交互流程、编译行为或排障结论变化时 |
| 串口通信协议正文 | 设备通信协议约定与仓库内实现 | `docs/developer/protocol.md` | 协议字段、链路约定、示例报文或硬件连接约束变化时 |
| `docs/superpowers` 协作文档归档规则 | `docs/superpowers/specs/` 与 `docs/superpowers/plans/` | `.agents/skills/reference-sync/references/superpowers-doc-archive.md` | specs / plans 归档口径、目录组织或入口引用规则变化时 |
| `problem_statement` 题面使用说明 | `docs/problem_statement/README.md` | `docs/problem_statement/README.md` | 题面文档结构、阅读顺序、维护方式或目录组织调整时 |
| `problem_statement` 来源与追溯 | `docs/problem_statement/sources.md` | `docs/problem_statement/sources.md` | 官方题面来源、抓取链路、本地产物映射或清洗依据变化时 |
| `problem_statement` 规格正文 | `docs/problem_statement/spec.md` | `docs/problem_statement/spec.md` | 官方规则正文更新、REQ 编号调整或需要补充规则事实时 |
| `problem_statement` 问答正文 | `docs/problem_statement/qa.md` | `docs/problem_statement/qa.md` | 官方问答新增、规则澄清变化或现有解释失效时 |
