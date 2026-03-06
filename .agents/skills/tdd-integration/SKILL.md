---
name: tdd-integration
description: Use when adding features or fixes in this repository to map superpowers TDD onto project-specific unit, contract, and HIL layers.
---

# Overview
将 superpowers 的 TDD 规则落地到本仓库的分层测试体系,避免只停留在原则层。

# Required Background
- **REQUIRED SUB-SKILL:** superpowers:test-driven-development

# When to Use
- 新增功能、修复问题、重构行为时
- 需要判断本次改动应先写哪一层测试时

# Layer Mapping
- `tests/unit/`：纯逻辑与确定性算法
- `tests/contract/`：命令处理器、协议路由、副作用契约
- `tests/hil/`：硬件与控制周期相关验证

# Execution Rules
1. 先写失败测试（RED）,并确认失败原因正确
2. 再写最小实现（GREEN）
3. 保持通过后再重构（REFACTOR）
4. 涉及硬件路径时,补充 `tests/hil/` 记录

# Quick Commands
```bash
python3 -m pytest tests/unit -q
python3 -m pytest tests/contract -q
python3 -m pytest tests/unit tests/contract -q
```

# Guardrails
- 不允许“先写代码后补测试”
- 不允许只做手工验证就宣称完成
- 若改动进入硬件耦合路径,必须保留 HIL 证据

# Deliverables
- 对应层级的失败测试与通过结果
- 必要的 HIL 记录
- 可复现的测试命令
