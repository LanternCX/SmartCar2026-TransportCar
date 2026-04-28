## Rules
1. 不要在撰写 skill 文档的时候展现任何的"历史性口吻"。例如：不再保留xxx，现在是xxx 等等携带时态的口吻，文档必须和当下代码对齐。如果携带历史性口吻会造成读者的困惑。历史变更已经在 git log 中有较为完整的体现了。
2. 如果发生了仓库的代码修改，需要检查本仓库是否和代码中的具体实现对齐。应该避免文档和实现出现较大差异。

## 说明
2. 本目录只存 Skill 实现、`references/` 与 `assets/`，技能索引也只维护在这里，避免污染仓库根 `AGENTS.md` 常驻上下文。
3. 仓库主入口与流程入口优先使用最短、最自然的名字。
4. 工具型 Skill 可使用 `*-tool` 后缀。
5. 扩展 superpowers 的本地 Skill 不得与上游同名覆盖，统一使用 `project-extension-*` 前缀。

## 当前 Skill 索引

- 用户主 review 正文优先看 `docs/developer/strategy.md`
- 其余 memory / TDD / Skill 写作方法正文不再作为用户主 review 正文, 相关规则改由对应 Skill 私有入口承接
- `using-rules`：仓库规则、协议、硬件事实和知识入口
- `reference-sync`：参考文档更新、外部资料同步、规则清洗入口
- `project-extension-writing-skills`：对 superpowers `writing-skills` 的本地扩展
- `project-extension-requesting-code-review`：对 superpowers `requesting-code-review` 的本地扩展
- `mpy-cli-tool`：`mpy-cli` 工具入口
- `git-workflow`：仓库 Git 流程规范入口
- `using-git-worktrees`：禁止默认 worktree 并重定向到本仓库 Git 流程
