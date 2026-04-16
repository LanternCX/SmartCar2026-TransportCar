# 注释规则

## 适用范围

- 本页用于统一维护仓库注释与文档字符串规则
- 实现阶段若需要补注释、审注释或调整注释风格, 优先回看本页
- 编码时应主动按本页补齐注释, 不要等 review 再回补
- 具体实现约束、测试约束与目录边界仍以 `implementation-rules.md` 为主

## 写作目标

- 注释首先是写给第一次接手这段代码的 maintainer 看的
- maintainer 在 review 改动时, 应该能只靠注释和代码, 大致明白这段逻辑在做什么
- 如果读完注释和代码后, 仍然说不清这一段的作用、边界或这样写的原因, 就说明注释还不够好
- 注释表达要简洁、准确、平实, 优先帮助人快速理解, 不要写成自我证明式说明

## 基础规则

- 注释与文档字符串统一使用中文
- 文档注释统一采用 Doxygen 风格
- 项目文档和代码注释只描述事实, 不使用历史性口吻
- 文档注释不要强调设计阶段口径, 优先说明文件、类、函数承担的职责和作用
- 注释标点统一使用半角符号并保持空格规则, 单行注释行尾不加收尾标点

## 显式注释要求

- 定义的变量要尽量补充注释, 说明角色、来源或用途
- 变量注释只描述变量本身的角色、来源、语义或用途, 不展开它参与的具体过程
- 所有配置项与全局常量都需要显式注释其语义、单位或边界含义
- 所有关键过程都需要显式注释其输入、输出或阶段目的
- 所有重难点过程都需要显式注释其约束、原因或容易误解的地方

## 补充要求

- 注释优先解释为什么这样做, 其次再解释做了什么
- 注释必须贴近被说明对象, 避免把多个含义混在一条注释里
- 若代码已由命名表达出基本含义, 注释就补充作用、边界和原因, 不要简单复述代码
- 注释默认使用陈述句, 仅在必要时补充解释
- 不要用 `关键过程`、`重难点` 这类机械标签式写法
- 不要在注释里重复变量名或代码已直接表达的信息
- 不要使用聊天式、口语化表述, 只保留帮助理解所需的信息

## 示例

```python
# 输入无效或过期时保持上一轮结果, 避免状态抖动
if prepared_observation.get("source_status") != "active":
    return dict(self.last_result)
```

```python
# 只保留对外输出所需字段, 避免内部状态外溢
self.last_result = {
    "selected_target": decision.selected_target,
    "phase": decision.phase,
    "assistant_command": self.last_assistant_command,
}
```

```python
# 给辅车的控制附带递增序号, 这样重复报文会被忽略
prepared_observation["control_seq"] = self.motion_runtime.next_control_seq()
```

```python
# 预留链路配置保留在入口对象中, 不参与决策
self.ingress = VisionIngress(
    active_uart=active_uart,
    reserved_uarts=reserved_uarts,
)
```

```python
"""主车应用编排入口

@file src/master/app.py
"""


class MasterApp:
    """负责串联视觉输入、决策输出和运行时状态

    @brief 对外提供主车应用的单步推进入口
    """
```
