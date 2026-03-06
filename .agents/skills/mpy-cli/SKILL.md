---
name: mpy-cli
description: Use when initializing, configuring, planning, deploying, or operating MicroPython device files in this repository through mpy-cli.
---

# Overview
统一本仓库 `mpy-cli` 的使用方式，覆盖初始化、配置、计划部署、执行部署与设备文件运维，减少手工 Thonny 操作和误刷风险。

# When to Use
- 首次在本仓库接入 `mpy-cli`
- 需要将本地 `src/` 代码同步到 MicroPython 设备
- 需要执行 `upload/run/delete/tree` 的设备文件运维
- 需要无交互批量部署

# Project Defaults
- 配置文件：`.mpy-cli.toml`
- 忽略文件：`.mpyignore`
- 运行目录：`.mpy-cli/`
- 当前仓库默认：`source_dir = "src"`、`device_upload_dir = ""`

# Core Semantics
- `.mpyignore` 规则匹配对象是“相对 `source_dir` 的路径”，不要写 `src/` 前缀
- `incremental`：按变更文件集增量同步（日常开发默认）
- `full`：清空 `device_upload_dir` 后全量重刷（高风险操作）

# Recommended Workflow
1. 初始化或重配：
   ```bash
   mpy-cli init
   mpy-cli config
   ```
2. 先预览：
   ```bash
   mpy-cli plan --mode incremental
   ```
3. 再部署：
   ```bash
   mpy-cli deploy --mode incremental
   ```
4. 自动化无交互部署：
   ```bash
   mpy-cli deploy --no-interactive --yes --port <PORT>
   ```

# Quick Commands
```bash
mpy-cli init [--force] [--no-interactive]
mpy-cli config
mpy-cli plan [--mode {incremental,full}] [--port PORT] [--no-interactive] [--yes]
mpy-cli deploy [--mode {incremental,full}] [--port PORT] [--no-interactive] [--yes]
mpy-cli upload [--local LOCAL] [--remote REMOTE] [--port PORT] [--no-interactive] [--yes]
mpy-cli run [--path PATH] [--port PORT] [--no-interactive] [--yes]
mpy-cli delete [--path PATH] [--port PORT] [--no-interactive] [--yes]
mpy-cli tree [--path PATH] [--port PORT] [--no-interactive]
```

# Safety Checklist
- 执行 `deploy` 前先跑 `plan`
- `full` 模式前确认目标设备和 `device_upload_dir`
- 串口被占用时先关闭 Thonny 等工具
- 无交互模式下显式传入 `--port` 与关键参数

# Troubleshooting
- `mpremote` 未安装：`python3 -m pip install mpremote`
- 串口连接失败：检查端口号并关闭占用串口的软件
- 不确定同步范围：先运行 `mpy-cli plan ...` 再执行 `deploy`

# Deliverables
- 可复现的部署命令（含模式与端口）
- 与 `source_dir` 一致的远端路径映射
- 计划输出与实际部署行为一致
