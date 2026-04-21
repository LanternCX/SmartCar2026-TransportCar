# 双仓库核心回归与行为测试补强实施计划

> 状态: Archive
> **给 Agent 工作者:** 必须使用 `superpowers:subagent-driven-development` 按任务逐项实现, 步骤统一使用复选框 `- [ ]` 维护执行状态。
> 当前约束以 `docs/superpowers/specs/archive/PR#50/2026-04-21-cross-repo-core-test-regression-design.md`、`tests/README.md` 与 `../SmartCar2026-Vision/AGENTS.md` 为准。

**目标:** 为车端仓库与 Vision 仓库补上一层更适合后续 TDD 的核心回归测试和行为测试, 并增加最小通信协议对齐测试。

**架构:** 先收敛测试边界, 只围绕核心行为与历史高风险回退点补测试。车端仓库负责消费与运行时行为回归, Vision 仓库负责观测到输出命令的行为回归, 双仓库之间再补最小协议对齐层, 避免口径漂移。

**技术栈:** Python、pytest、车端 `tests/unit`/`tests/contract`、Vision `tests/unit`/`tests/contract`

---

## 文件范围与职责

- 修改: `tests/unit/test_master_forward_runtime.py`
  - 补主车关键转发与异常行为回归。

- 修改: `tests/unit/test_assistant_follow_runtime.py`
  - 补辅车关键融合与异常行为回归。

- 修改: `tests/unit/test_remote_control_role_dispatch.py` 或 `tests/unit/test_role_vision_layer_factory.py`
  - 补角色入口的最小外部行为测试。

- 修改: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
  - 补 Vision 主链路的关键行为回归。

- 修改: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
  - 补最小输出协议契约。

- 新增或修改: 双方现有 contract / unit 测试文件
  - 固定最小通信协议对齐语义。

## Task 1: 盘点并补车端核心行为回归

**Files:**
- 修改: `tests/unit/test_master_forward_runtime.py`
- 修改: `tests/unit/test_assistant_follow_runtime.py`
- 修改: `tests/unit/test_remote_control_role_dispatch.py`
- 修改: `tests/unit/test_role_vision_layer_factory.py`

- [ ] 找出现有测试还没有覆盖、但后续最容易被改坏的车端核心行为。
- [ ] 先补主车关键转发与异常不中断的回归测试。
- [ ] 再补辅车关键融合、位置/速度切换和异常场景的行为测试。
- [ ] 若角色分流仍缺少最小行为保护, 在入口测试中补齐。
- [ ] 运行车端定向测试, 确认新增测试通过且不过度绑定实现细节。

## Task 2: 盘点并补 Vision 核心行为回归

**Files:**
- 修改: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- 修改: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

- [ ] 找出现有 Vision 测试还没有覆盖、但后续调算法和协议时最容易回退的核心行为。
- [ ] 补无目标、保持、单轴偏差、双轴偏差、关键方向性这类行为测试。
- [ ] 对已经被证明是正式主线的输出口径继续保留强契约。
- [ ] 运行 Vision 定向测试, 确认新增测试通过且没有重新绑定内部阶段名或实现路径。

## Task 3: 补双仓库最小协议对齐测试

**Files:**
- 修改: `tests/contract/` 下现有协议相关测试
- 修改: `../SmartCar2026-Vision/tests/contract/` 下现有协议相关测试

- [ ] 明确双方共同依赖的最小文本协议面。
- [ ] 在 Vision 侧补“输出什么”的契约测试。
- [ ] 在车端侧补“当前认什么”的契约测试。
- [ ] 确保关键字段、零值语义和旧字段禁用口径在两边一致。

## Task 4: 全量回归与收口

**Files:**
- 修改: 如上测试文件

- [ ] 运行车端主机侧相关测试集合。
- [ ] 运行 Vision 主机侧相关测试集合。
- [ ] 复查新增测试是否存在新的过度约束。
- [ ] 如有必要, 对测试名和注释做最小整理, 让后续 TDD 更容易定位。
- [ ] 完成后把 spec / plan 状态更新为 `Archive`。
