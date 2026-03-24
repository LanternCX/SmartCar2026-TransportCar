---
name: mpy-cli-tool
description: Use when initializing, configuring, scanning ports, planning, deploying, or operating MicroPython device files through mpy-cli, especially when questions involve command flags, non-interactive runs, cross-project setup, or path mapping to source_dir and device_upload_dir.
---

# mpy-cli 工具

## Overview
统一本仓库 `mpy-cli` 的使用入口。主文档只保留命令索引、场景路由和高风险边界; 详细正文放在 `references/` 指向的唯一文档中。

## When to Use
- 首次在本仓库接入 `mpy-cli`
- 不确定设备当前串口，需先发现可用 MicroPython 设备
- 需要将本地 `src/` 代码同步到 MicroPython 设备

- 需要执行 `upload/run/delete/tree` 等设备文件运维
- 用户在问 `--base`、`--scan-mode`、路径映射和部署边界细节

## Command Index
- 初始化或重配：`init`, `config`
- 发现设备：`list`
- 部署主流程：`plan`, `deploy`
- 单文件运维：`upload`, `run`, `delete`, `tree`

## Routing Rules
- 想先知道有哪些命令，或确认 `source_dir`、`device_upload_dir`、`.mpyignore` 边界 -> `references/command-and-path-boundaries.md`
- 想排查端口、扫描、部署失败 -> `references/troubleshooting.md`

## Safety Gates
- 串口未知时先 `mpy-cli list`
- 部署前先 `mpy-cli plan`
- `full` 模式前必须确认目标设备与上传目录边界

## Deliverables
- 可复现的命令选择
- 对应 reference 的查询路径
- 明确的部署边界说明
