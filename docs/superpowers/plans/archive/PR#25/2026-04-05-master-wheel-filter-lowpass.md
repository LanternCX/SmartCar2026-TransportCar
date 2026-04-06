# 主车轮速回归滤波替换为一阶低通实现计划

> **给执行 Agent 的要求:** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。本计划使用 `- [ ]` 复选框跟踪步骤。

**目标:** 在不扩大到辅车和其他控制链的前提下，把主车轮速滤波链中的双窗口回归段替换为更轻的一阶低通段，降低主车热路径运行负担。

**架构:** 保留当前“尖峰压制 -> 差分限幅 -> 最后一段滤波”的三段结构，只替换最后一段。外部参数入口暂时保持不变，在主车滤波模块内部把现有窗口参数折算成等效低通强度，避免本轮扩大成参数体系重写。

**技术栈:** Python, pytest, 主车 runtime 主线, `src/master/ctrl/filters.py`, `src/master/motion_runtime.py`

---

## 执行边界

- 本轮只改 `src/master/`。
- 本轮只改轮速滤波链中的回归段, 不顺手改姿态低通、PID、运动学、视觉链和辅车实现。
- 外部参数口径先保持不变, 不把本轮扩大到 `runtime_params.py` 的命名重写。
- 每次真正执行 `git commit` 前, 仍然先向用户确认提交消息。

### Task 1: 锁定主车滤波替换测试边界

**Files:**
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/master/test_motion_runtime.py`
- Verify: `src/master/ctrl/filters.py`

- [ ] Step 1: 先补主车轮速滤波链失败测试，明确本轮只替换主车回归段，不再要求主辅默认输出完全一致
- [ ] Step 2: 补一条主车滤波链对尖峰样本仍有抑制的边界测试，确保一阶低通不会让异常样本原样直通
- [ ] Step 3: 补一条主车运行时仍能正常装配轮速滤波链的测试，确保替换后主线装配不回退
- [ ] Step 4: 运行主车相关测试，确认新测试先红灯，失败原因确实指向尚未完成的滤波替换

### Task 2: 在主车滤波模块内部替换回归段

**Files:**
- Modify: `src/master/ctrl/filters.py`
- Verify: `src/master/runtime_params.py`

- [ ] Step 1: 保留尖峰压制和差分限幅两段, 只把最后的双窗口回归对象替换为一阶低通对象
- [ ] Step 2: 在滤波模块内部增加旧窗口参数到低通强度的折算逻辑, 不改外部参数入口名字
- [ ] Step 3: 删除主车轮速链对长短窗口历史和回归预测状态的依赖, 让最后一段只保留最小跨周期状态
- [ ] Step 4: 运行滤波相关测试，确认新的低通链已经把 Task 1 的红灯转绿

### Task 3: 接回主车运行时装配并做回归验证

**Files:**
- Modify: `src/master/motion_runtime.py`
- Modify: `tests/unit/master/test_motion_runtime.py`
- Verify: `tests/unit/master/`

- [ ] Step 1: 复查主车运行时装配点，确认它仍然只是在原位置装配新的滤波链，不新增新的 owner 或额外缓存
- [ ] Step 2: 运行主车与滤波替换直接相关的测试，确认轮速闭环主线没有被带坏
- [ ] Step 3: 运行整组 `tests/unit/master`，确认主车主线整体仍然通过
- [ ] Step 4: 记录这轮替换后的板端待验证重点：视觉接入后长期运行是否更稳、轮速响应是否明显变拖、尖峰样本是否仍被压住

### Task 4: 收口本轮结论并准备后续板端验证

**Files:**
- Verify: `docs/superpowers/specs/2026-04-05-master-wheel-filter-lowpass-design.md`
- Verify: `tests/unit/master/`
- Verify: `tests/hil/`

- [ ] Step 1: 复核本轮是否严格保持在“只改主车回归段”的边界内
- [ ] Step 2: 汇总主机测试结果，明确本轮已经证明的内容和仍需上板确认的内容
- [ ] Step 3: 若继续板端验证，优先观察视觉接入后的长期运行稳定性，而不是先扩大到更多控制语义调整

### Task 5: 执行板端验证并补齐 HIL 留证

**Files:**
- Modify: `tests/hil/2026-03-master-minimal-runtime.md`
- Verify: `docs/superpowers/specs/2026-04-05-master-wheel-filter-lowpass-design.md`
- Verify: `src/master/ctrl/filters.py`
- Verify: `src/master/motion_runtime.py`

- [ ] Step 1: 在现有主车板端验证文档里补一段本轮滤波替换专项留证区，写清基线版本、验证时间、板端环境和当前专项目标
- [ ] Step 2: 先完成 `stage2` 级别验证，至少记录设备连接、上传、启动、smoke 输出和最小诊断面是否仍可用
- [ ] Step 3: 在接入视觉的当前主线下继续观察一段时间，记录是否仍出现内存报错，以及替换后是否出现明显变拖或明显发散
- [ ] Step 4: 把板端验证结果写回 HIL 文档，至少包含操作步骤、关键观测、失败归因或通过结论，不留“以后再补”的空档
- [ ] Step 5: 最后把主机测试结论和板端留证一起收口，明确这轮到底是“主机侧完成但板端待继续”，还是“主机与板端都已完成”
