---
name: mpy-cli-tool
description: Use when initializing, configuring, scanning ports, planning, deploying, or operating MicroPython device files through mpy-cli, especially when questions involve command flags, non-interactive runs, cross-project setup, or path mapping to source_dir and device_upload_dir.
---

# mpy-cli 工具

## 概述
这里是 `mpy-cli` 的统一入口。主 Skill 只保留命令索引、场景路由和高风险边界，完整命令手册统一维护在 `references/mpy-cli-manual.md`。

## 适用场景
- 首次在本仓库接入 `mpy-cli`
- 不确定设备当前串口，需先发现可用 MicroPython 设备
- 需要将本地 `src/` 代码同步到 MicroPython 设备

- 需要执行 `upload/run/delete/tree` 等设备文件运维
- 用户在问 `--base`、`--scan-mode`、路径映射和部署边界细节

## 命令索引
- 初始化或重配：`init`, `config`
- 发现设备：`list`
- 部署主流程：`plan`, `deploy`
- 单文件运维：`upload`, `run`, `delete`, `tree`

## 手册入口
- 完整命令手册：`references/mpy-cli-manual.md`
- 需要查参数、无交互调用、安装方式、路径映射和常见问题时，优先进入该手册

## 路由规则
- 想先知道有哪些命令，或确认 `source_dir`、`device_upload_dir`、`.mpyignore` 边界 -> `references/command-and-path-boundaries.md`
- 想排查端口、扫描、部署失败 -> `references/troubleshooting.md`
- 需要完整正文时，以上入口页都应继续路由到 `references/mpy-cli-manual.md`

## 安全门禁
- 串口未知时先 `mpy-cli list`
- 部署前先 `mpy-cli plan`
- `full` 模式前必须确认目标设备与上传目录边界

## 交付目标
- 可复现的命令选择
- 对应 reference 的查询路径
- 明确的部署边界说明
