# 串口协议文档与 Skill 约束同步执行 Plan

执行状态：Archive  
创建日期：2026-04-25  
对应 Spec：`docs/superpowers/specs/2026-04-25-serial-protocol-doc-and-skill-sync-spec.md`

## 目标

把正式串口协议正文迁入 `docs/developer/protocol.md`，并同步更新开发者文档入口、Skill 路由和参考同步登记。

## 范围

只修改文档和 Skill 规则，不修改运行时代码，不新增测试，不做 git 操作。

## 文件变更

- 新增：`docs/developer/protocol.md`
- 修改：`docs/developer/control.md`
- 修改：`docs/developer/vision.md`
- 修改：`docs/AGENTS.md`
- 修改：`README.md`
- 修改：`.agents/skills/using-rules/SKILL.md`
- 修改：`.agents/skills/using-rules/references/hardware-protocol.md`
- 修改：`.agents/skills/using-rules/references/control-vision-runtime.md`
- 删除：`.agents/skills/using-rules/references/openart-protocol.md`
- 修改：`.agents/skills/reference-sync/references/source-registry.md`
- 修改：`.agents/skills/reference-sync/references/maintenance-checklist.md`
- 修改：本 Spec 和本 Plan 的执行状态

## 执行步骤

- [x] 新增 `docs/developer/protocol.md`，写入 UDP / TCP 双模式协议正文。
- [x] 在 `control.md` 和 `vision.md` 中加入协议正文入口，并移除查询协议作为正式主线的表达。
- [x] 更新 `README.md` 与 `docs/AGENTS.md`，加入协议文档入口。
- [x] 更新 `using-rules` 主入口和硬件协议规则页，把完整协议正文路由到 `docs/developer/protocol.md`。
- [x] 删除旧 Skill 私有协议正文，避免继续保留兼容层。
- [x] 更新 `reference-sync` 来源登记和维护清单，把协议正式落点改为 `docs/developer/protocol.md`。
- [x] 将 Spec 和 Plan 执行状态标记为 `Archive`。
- [x] 做文本自检，确认旧协议事实源、查询协议正式主线和兼容层说明不再残留在当前入口文档中。

## Review 检查

- [x] 正式协议正文只在 `docs/developer/protocol.md`。
- [x] 高频 UDP 包强调短包和最新优先。
- [x] 低频 TCP 同步强调重复发送、ACK 和幂等。
- [x] 车端通用状态查询不作为正式主线保留。
- [x] 文档没有保留旧协议兼容层。
- [x] Skill 只做路由和约束，不承载完整协议正文。
