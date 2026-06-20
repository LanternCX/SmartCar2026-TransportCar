# 文档与注释规则

## 适用范围

- 本页用于项目文档、Skill 文档、代码注释和文档字符串的写作规则。
- 文档、注释和 Skill 正文改动不使用 TDD; 完成时通过 review 做规则检查。
- 具体实现约束、测试约束与目录边界以 `implementation-core.md` 为主。

## 写作目标

- 文档和注释首先服务第一次接手这段内容的 maintainer。
- 读者应能只靠正文和附近代码, 大致明白职责、边界和使用方式。
- 表达要简洁、准确、平实, 不写自我证明式说明。
- 只描述当前事实, 不使用历史性口吻。

## 项目文档规则

- 仓库新建文档统一使用中文。
- 正式开发文档优先放在 `docs/developer/` 或 `docs/problem_statement/` 的对应目录。
- `docs/developer/` 优先承载外部约定、项目决策和职责边界。
- `docs/developer/` 只写代码外事实, 不镜像代码已经表达的流程、字段表、状态表、测试路径或参数细节。
- Agent 理解代码功能时优先读代码、注释和行为测试, 因为这些事实更接近实现并能被测试约束。
- 文档没有代码同等粒度的测试保护, 复制代码功能说明会增加同步风险。
- 局部设计原因优先由贴近代码的注释承载, 长期协作结论写入 Serena memory。
- 新增主入口或一级目录后同步更新 `docs/AGENTS.md`。
- 文档正文不要维护兼容层说明、多套字段双轨说明或过期路径镜像。
- 需要历史追溯、阶段取舍或事故背景时依赖 git 历史或 Serena memory, 不把历史解释写进正式正文。
- 可复用设计取舍、调试结论和阶段闭环优先写入 Serena memory, 不塞回正式开发文档正文。

## Skill 文档规则

- 仓库新建 Skill 与 Skill reference 统一使用中文。
- 主 `SKILL.md` 默认只做用途、边界和最短路由说明。
- `references/` 只保留有明确场景差异的入口; 没有差异就合并。
- reference 的目标是降低选择成本, 不是展示分类完整性。
- Skill 结构、路由和 reference 布局规则以 `.agents/skills/project-extension-writing-skills/` 为准。

## 注释与文档字符串规则

- 代码注释与文档字符串统一使用中文。
- 文档注释统一采用 Doxygen 风格。
- 注释标点统一使用半角符号, 半角标点后面加空格。
- 单行注释行尾不加收尾标点。
- 文档注释不要强调设计阶段口径, 优先说明文件、类、函数承担的职责和作用。
- 注释优先解释为什么这样做, 其次解释做了什么。
- 若代码命名已经表达基本含义, 注释补充作用、边界和原因, 不简单复述代码。

## 显式注释要求

- 变量注释说明角色、来源、语义或用途, 不展开它参与的具体过程。
- 配置项与全局常量需要说明语义、单位或边界含义。
- 关键过程需要说明输入、输出或阶段目的。
- 重难点过程需要说明约束、原因或容易误解的地方。
- 注释必须贴近被说明对象, 避免多个含义混在一条注释里。
- 不使用 `关键过程`、`重难点` 这类机械标签式写法。
- 不使用聊天式、口语化表述。

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
"""主车角色运行时

@file src/vision/master/forward_runtime.py
"""


class MasterForwardRuntime:
    """负责主车视觉输入、状态机推进和主辅同步编排

    @brief 对外提供主车角色的单步推进入口
    """
```
