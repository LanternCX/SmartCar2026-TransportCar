---
name: control-system
description: Use when implementing, tuning, or debugging motion control logic such as PID loops, kinematics, odometry, and trajectory behavior.
---

# Overview
规范控制算法开发与调参流程，重点保证系统稳定性、可解释性和可回归验证。

# When to Use
- 新增或修改 PID、运动学、里程计、轨迹或控制模式
- 处理振荡、迟滞、稳态误差、航向漂移等控制问题
- 为新地面/配重重做参数辨识和整车联调

# Control Model
- 控制层级：位置环（外环） -> 速度环（内环） -> PWM 输出
- 反馈来源：编码器（速度/里程计）+ IMU（航向）
- 模式：速度模式、位置模式、角度保持模式

# Development Rules
- 改算法前先确认硬件基线：编码器方向、电机方向、IMU 校准
- 参数辨识先行：使用 `pid_identify.py` 生成最新电机参数
- 关键参数统一在 `config/params.py`，禁止散落阈值
- 任何跨模块改动需保持 `services/` 只做编排，算法实现留在 `control/` 和 `filters/`
- 控制周期预算默认 5ms，新增计算必须评估耗时

# Tuning Workflow
1. 校准陀螺仪：`calibrate_gyro.py`
2. 重新辨识电机：`pid_identify.py`
3. 只开速度环调内环（先稳后快）
4. 打开位置环调外环（关注过冲与收敛）
5. 调航向保持（抗扰与长期漂移）
6. 做组合轨迹联调（x/y/angle + lock 逻辑）

# Fast Diagnostics
- 振荡：先降 P，再增 D，检查滤波与周期抖动
- 响应慢：增 P、减滤波延迟、核对前馈
- 稳态误差：补 I 或校正前馈、复核辨识参数
- 航向漂移：重做 IMU 零漂，检查积分与 `dt`
- 轨迹偏差：检查打滑、最大速度、加速度限制

# Validation Checklist
- 单轮和三轮协同控制均通过
- 速度模式、位置模式、模式切换均通过
- `?lock` 相关行为与相对位移命令一致
- 长时间运行无明显航向漂移失控

# Git Policy
- 分支策略与提交规范只使用 `.agents/skills/git-workflow/SKILL.md`
- 不要使用 superpowers 自带的 git workflow 作为本项目规范

# Deliverables
- 控制算法或参数变更说明
- 调参与验证记录（步骤 + 现象 + 结论）
- 必要时补充回归测试脚本或验证命令
