---
name: remote-spec-to-markdown
description: Use when remote competition rule pages need to be imported into repository markdown with cleaned content, preserved images, and traceable sources for agent reading.
---

# Overview

将远端网页题面抓取为仓库内 Markdown，保留正文图片与来源追溯，清理页面噪声，输出可直接供 Agent 检索的规则文档。

# When to Use

- 题面规则在 CSDN/博客/官网网页而不在仓库内。
- 需要让 Agent 在本地直接读取、引用、比对规则。
- 页面包含图片、问答澄清、章节化条款。

# Inputs

- `urls`: 需要抓取的网页链接列表。
- `output_dir`: 默认 `docs/problem_statement`。
- `topic`: 主题标识（可选，用于命名归档）。

# Outputs

- `docs/problem_statement/spec.md`：主规则（总则 + 组别细则 + REQ 索引）。
- `docs/problem_statement/qa.md`：问答澄清。
- `docs/problem_statement/sources.md`：来源追溯与清洗策略。
- `docs/problem_statement/README.md`：使用说明。

# Workflow

1. 抓取所有 URL 原文内容。
2. 按正文边界提取主体，删除站点噪声。
3. 统一标题层级，保留正文图片链接与图注。
4. 将总则与细则合并为 `spec.md`。
5. 将问答整理为 `qa.md`，按时间分组。
6. 生成 `REQ-*` 编号供开发与测试引用。
7. 写入 `sources.md` 记录 URL 与清洗说明。

# Cleaning Rules (CSDN)

- 保留：文章标题、章节正文、表格/问答、正文图片与图注。
- 删除：点赞、收藏、评论、分享、打赏、推荐、作者侧栏、广告、上一篇下一篇。
- 图片策略：
  - 保留正文图（常见为 `i-blog.csdnimg.cn`）；
  - 过滤站点 UI 图标（常见为 `csdnimg.cn/release/blogv2`）。
- 链接策略：去除追踪参数，过滤 `javascript:` 无效链接。

# REQ 编号建议

- `REQ-GEN-*`：总则与通用约束。
- `REQ-ANT-*`：蚂蚁搬家细则。
- `REQ-QA-*`：问答澄清。

# Validation Checklist

- `spec.md`、`qa.md`、`sources.md` 文件存在。
- 文档中不含明显页面噪声词（如“打赏/上一篇/热门文章”）。
- 关键数值限制完整（尺寸、计时、重量、障碍）。
- 每条 REQ 能追溯到来源 URL。

# Common Mistakes

- 只复制网页，不清洗噪声，导致 Agent 检索失焦。
- 丢失图片链接与图注，导致规则图信息缺失。
- 未编号 REQ，后续实现无法稳定引用。
