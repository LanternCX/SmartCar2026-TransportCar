# 参考文档维护清单

## 使用说明

- 本页用于持续维护，不承接正式正文。
- 每次更新正式正文或题面文档集时，都要同时核对来源、正式落点和检查项是否仍然成立。
- 新增长期维护对象时，先补本页，再补 `source-registry.md`。

## 维护 checklist

### `mpy-cli` 正式文档

- 来源：`@../mpy-cli-dev` 仓库中的 `README.md`、`docs/developer-guide.md`、`mpy_cli/`、`tests/`
- 正式落点：`@../mpy-cli-dev`
- 维护检查项：
  - [ ] 命令与参数说明仍和当前工具行为一致
  - [ ] 路径边界、`source_dir`、`device_upload_dir` 等约定没有过期
  - [ ] 当前仓库的 Skill 与轻量入口页仍能路由到 `@../mpy-cli-dev`
  - [ ] 本页与 `source-registry.md` 的来源和落点描述一致

### 串口通信协议正文

- 来源：协议原始约定、仓库内当前实现和协作过程形成的低带宽约束
- 正式落点：`docs/developer/protocol.md`
- 维护检查项：
  - [ ] 协议字段、链路约定和示例报文仍然有效
  - [ ] `using-rules` 入口页仍能路由到正式正文
  - [ ] 正文没有混入来源追溯类维护信息
  - [ ] 正文没有维护其他格式兼容层或多套字段双轨说明
  - [ ] 本页与 `source-registry.md` 的来源和落点描述一致

### `docs/superpowers` 协作文档归档规则

- 来源：仓库内 specs / plans 协作流程与归档约定
- 正式落点：`.agents/skills/reference-sync/references/superpowers-doc-archive.md`
- 维护检查项：
  - [ ] specs / plans 根目录和 archive 目录规则仍然有效
  - [ ] 当前入口文档没有继续路由到 `using-rules` 的归档页
  - [ ] 搬运规则没有混入具体设计正文或执行正文
  - [ ] 本页与 `source-registry.md` 的来源和落点描述一致

### `problem_statement` 文档集

- 来源：官方题面、官方问答、题面抓取与清洗记录、仓库内既有维护文档
- 正式落点：`docs/problem_statement/README.md`、`docs/problem_statement/sources.md`、`docs/problem_statement/spec.md`、`docs/problem_statement/qa.md`
- 维护检查项：
  - [ ] `README.md`、`sources.md`、`spec.md`、`qa.md` 四个对象都仍在维护范围内
  - [ ] 官方规则或问答变化后，规格正文与问答正文已同步复核
  - [ ] 来源追溯、抓取依据、本地产物映射仍可复查
  - [ ] 本页与 `source-registry.md` 的对象列表保持一致
