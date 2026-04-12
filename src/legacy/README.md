# legacy 冻结参考基线

- `src/legacy` 是旧系统代码的实际归档位置, 用于完整保留原运行时主干
- 本目录只作为冻结参考基线, 不再承载后续功能演进
- 新系统不得直接依赖 `src/legacy`, 后续实现仅在 `src/master` 与 `src/assistant` 中推进
