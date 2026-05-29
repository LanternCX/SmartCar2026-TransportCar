# 参考文档维护清单

## 使用说明

- 本页用于持续维护，不承接正式正文。
- 每次更新正式正文或外部链接入口时，都要同时核对来源、正式落点和检查项是否仍然成立。
- 新增长期维护对象时，先补本页，再补 `source-registry.md`。
- 外部资料、官方题面、官方问答或 GitHub PR 状态可能变化时，必须通过联网核对、用户提供的官方资料或本地可验证记录确认来源。
- 外部题面资料只维护链接入口，不导入本地正文。

## 维护 checklist

### `mpy-cli` 正式文档

- 正式落点：`@../mpy-cli-dev`
- 维护检查项：
  - [ ] 命令与参数说明仍和当前工具行为一致
  - [ ] 路径边界、`source_dir`、`device_upload_dir` 等约定没有过期
  - [ ] Skill 入口页仍能路由到 `@../mpy-cli-dev`
  - [ ] 本页与 `source-registry.md` 的对象和触发条件一致

### 串口通信协议正文

- 正式落点：`docs/developer/protocol.md`
- 维护检查项：
  - [ ] 协议字段、链路约定和示例报文仍然有效
  - [ ] `using-rules` 入口页仍能路由到正式正文
  - [ ] 正文没有混入来源追溯类维护信息
  - [ ] 正文没有维护其他格式兼容层或多套字段双轨说明
  - [ ] 本页与 `source-registry.md` 的对象和触发条件一致

### `wireless_uart` 参考文档

- 正式落点：`docs/reference/wireless_uart/README.md`
- 维护检查项：
  - [ ] 原始项目链接与说明书链接仍然可用或已替换为新的有效来源
  - [ ] 本地只保留整理后的 Markdown 与配图, 不再恢复 PDF 副本
  - [ ] 配图目录与正文引用保持一致, 没有失效链接
  - [ ] 本页与 `source-registry.md` 的对象和触发条件一致

### `docs/superpowers` 协作文档归档规则

- 正式落点：`.agents/skills/reference-sync/references/superpowers-doc-archive.md`
- 维护检查项：
  - [ ] specs / plans 根目录和 archive 目录规则仍然有效
  - [ ] 归档所依赖的 PR 状态已通过本地 git、GitHub 或用户确认
  - [ ] 搬运规则没有混入具体设计正文或执行正文
  - [ ] 本页与 `source-registry.md` 的对象和触发条件一致

### `problem_statement` 外部链接入口

- 正式落点：`docs/problem_statement/README.md`
- 维护检查项：
  - [ ] 总则、蚂蚁搬家细则、细则镜像和问答入口链接仍然可用或已标注不可用
  - [ ] 本地没有恢复题面正文、问答正文、清洗副本或 REQ 编号镜像
  - [ ] 规则相关开发任务能从 README 直接跳到外部来源
  - [ ] 本页与 `source-registry.md` 的对象列表保持一致
