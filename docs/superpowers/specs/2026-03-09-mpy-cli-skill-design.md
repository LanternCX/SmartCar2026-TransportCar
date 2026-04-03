# mpy-cli Skill 补齐设计

## 背景

当前仓库正式手册 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` 已补充 `list` 命令、串口扫描策略，以及 `device_upload_dir`、`.mpyignore`、`run/delete/tree` 的路径语义。

但当时的 `.agents/skills/mpy-cli/SKILL.md` 仍停留在较早版本，主要覆盖 `init/config/plan/deploy/upload/run/delete/tree` 的基础流程，没有把新近落地的端口发现与路径边界补进来。现行入口已迁到 `.agents/skills/mpy-cli-tool/SKILL.md`。

这会导致 agent 在真实设备操作场景中出现两个风险：

- 串口未知时仍要求用户直接提供 `--port`，而不是先用 `mpy-cli list` 发现设备
- 对 `full` 模式清理范围、`device_upload_dir` 前缀、以及 `run/delete/tree` 的路径语义理解不完整

## 设计目标

1. 让 `mpy-cli` skill 与当前正式手册 `.agents/skills/mpy-cli-tool/references/mpy-cli-manual.md` 的关键能力对齐。
2. 保持 skill 为“agent 决策准则”，而不是膨胀成完整命令手册。
3. 在不重写全文风格的前提下，补齐端口发现、安全边界和路径语义。

## 设计结论

### 结构策略

采用保守补齐方案，保留现有 `Overview`、`When to Use`、`Project Defaults`、`Core Semantics`、`Recommended Workflow`、`Quick Commands`、`Safety Checklist`、`Troubleshooting`、`Deliverables` 主结构，只在关键节点增补缺失信息。

### 新增能力入口

把 `mpy-cli list` 提升为 skill 中的正式入口，而不是留给用户手册承担。agent 在以下场景应优先想到 `list`：

- 不知道设备当前串口
- 多块板并存，需要先识别可用设备
- 已知端口可能失效，需要重新探测

skill 将明确：串口未知时，先 `mpy-cli list`；已知端口且目标是同步代码时，再进入 `plan -> deploy`。

### 核心语义补齐

在 `Core Semantics` 中补齐以下决策级语义：

- `.mpyignore` 匹配对象是相对 `source_dir` 的路径，不带 `src/` 前缀；历史 `src/...` 写法应迁移
- `device_upload_dir` 是设备端上传前缀；`full` 模式只清空该目录，不清空整机根目录
- `run/delete/tree` 的 `--path` 语义都是相对 `device_upload_dir`
- `list` 默认优先探测成功缓存端口与当前可用端口交集，若未发现设备，再回退到当前端口全量探测

### 推荐流程调整

把推荐流程细化为：

1. 首次接入或配置变化时执行 `init/config`
2. 串口未知时先 `list`
3. 部署前先 `plan --mode incremental`
4. 确认计划后再 `deploy`
5. 单文件运维使用 `upload/run/delete/tree`

这样 skill 能引导 agent 先解决“连到哪块板”问题，再进入同步与执行流程。

## 错误处理

skill 的故障入口保持轻量，但覆盖高频决策：

- `mpremote` 缺失：安装 `mpremote`
- 串口连接失败：核对端口并关闭占用软件
- 端口未知或扫描结果不稳定：先 `mpy-cli list`，必要时使用扫描参数
- 同步范围不确定：回到 `mpy-cli plan`
- `full` 风险不明：重新核对 `device_upload_dir` 与目标端口

## 验证策略

本次更新以“文档一致性验证”为主，不新增代码测试框架：

1. 基线验证当前 skill 在“串口未知”场景下确实遗漏 `list`
2. 更新 skill 后重新核对其是否覆盖 docs 中以下关键点：
   - `list` 命令与扫描参数
   - `device_upload_dir` / `.mpyignore` 语义
   - `run/delete/tree` 的相对路径语义
   - `full` 模式清理边界
3. 保持文档语言为中文，且不把 skill 扩写成完整参考手册

## 交付物

- 更新后的 `.agents/skills/mpy-cli/SKILL.md`
- 与本次修改相匹配的实现计划文档
