## Rules
1. Skill 文档只描述当前事实、当前职责和当前路由，不写迁移解释、版本对比或历史变更说明。
2. 修改 Skill 文档时，先核对本目录索引、相关 `references/`、正式代码与正式开发文档，避免入口和实现脱节。
3. 规则按渐进式路径组织：主入口只给用途、边界和路由；具体规则放入最少数量的 reference 页；高风险细节只在触发场景下加载。

## Directory Rules
1. 本目录只存 Skill 实现、`references/` 与 `assets/`；Skill 索引维护在本文件。
2. 仓库主入口与流程入口优先使用最短、最自然的名字。
3. 工具型 Skill 可使用 `*-tool` 后缀。
4. 扩展 superpowers 的本地 Skill 不与上游同名覆盖，统一使用 `project-extension-*` 前缀。

## Skill Index

- `using-rules`：实现前与实现中的仓库规则、协议、硬件事实和知识入口
- `project-extension-requesting-code-review`：任务收口、评审门禁与内存自检入口
- `reference-sync`：参考链接、来源追溯、维护清单与协作文档归档入口
- `project-extension-writing-skills`：Skill 新建、重构、迁移与写作规范入口
- `mpy-cli-tool`：`mpy-cli` 工具使用、路径边界和排障入口
- `git-workflow`：仓库 Git Flow 与 Angular Conventional Commit 规范入口
- `using-git-worktrees`：worktree 触发场景的本地 Git 流程重定向入口
