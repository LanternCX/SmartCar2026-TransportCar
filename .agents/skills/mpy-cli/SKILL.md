---
name: mpy-cli
description: Use when initializing, configuring, scanning ports, planning, deploying, or operating MicroPython device files through mpy-cli, especially when questions involve command flags, non-interactive runs, cross-project setup, or path mapping to source_dir and device_upload_dir.
---

# Overview
统一本仓库 `mpy-cli` 的使用方式，覆盖安装、初始化、配置、端口发现、计划部署、执行部署与设备文件运维，减少手工 Thonny 操作和误刷风险。

# When to Use
- 首次在本仓库接入 `mpy-cli`
- 需要在其他项目中安装并复用 `mpy-cli`
- 不确定设备当前串口，需先发现可用 MicroPython 设备
- 需要将本地 `src/` 代码同步到 MicroPython 设备
- 需要执行 `upload/run/delete/tree` 的设备文件运维
- 需要无交互批量部署
- 用户在问 `--base`、`--scan-mode`、短参数别名或路径映射细节

# Environment
- Python：`>= 3.10`，推荐 `3.11`
- 依赖：已安装 Git，开发机可访问 MicroPython 设备串口
- 仓库内开发安装：
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python3 -m pip install --upgrade pip
  python3 -m pip install -e ".[dev]"
  python3 -m pytest -q
  ```

# Project Defaults
- 配置文件：`.mpy-cli.toml`
- 忽略文件：`.mpyignore`
- 运行目录：`.mpy-cli/`
- 当前仓库默认：`source_dir = "src"`、`device_upload_dir = ""`

# Core Semantics
- `.mpyignore` 规则匹配对象是“相对 `source_dir` 的路径”，不要写 `src/` 前缀
- 若历史 `.mpyignore` 规则带有 `src/...` 前缀，需要迁移为相对 `source_dir` 的写法
- `source_dir` 是本地源码根目录；远端路径映射以它为根，不保留此前缀
- 当 `source_dir = "src"` 时，本地 `src/main.py` 对应远端 `:main.py`
- `device_upload_dir` 是设备端上传目录前缀；留空表示设备根目录
- 当 `device_upload_dir = "apps/demo"` 时，本地 `main.py` 会上传到 `:apps/demo/main.py`
- `incremental`：按变更文件集增量同步（日常开发默认）
- `plan/deploy --base <COMMIT>` 仅在 `incremental` 模式生效，增量集合按“基准提交 vs 当前工作区”计算
- `full`：清空 `device_upload_dir` 后全量重刷（高风险操作），不会清空整机设备根目录
- `run/delete/tree` 的 `--path` 语义都是相对 `device_upload_dir`；`tree` 不传 `--path` 时默认读取该目录根
- `delete` 指向目录时默认递归删除整个目录
- `list` 默认优先探测成功缓存端口与当前可用端口的交集；若未发现设备，再回退到当前端口全量探测
- 当前可用端口以 `mpremote connect list` 结果为准，兼容 macOS / Linux / Windows（如 `COM3`）
- 若存在 `.mpy-cli.toml`，`list` 会优先使用其中的 `mpremote_binary`；否则默认 `mpremote`

# Recommended Workflow
1. 初始化或重配：
   ```bash
   mpy-cli init
   mpy-cli config
   ```
2. 串口未知时先发现设备：
   ```bash
   mpy-cli list
   ```
3. 先预览：
   ```bash
    mpy-cli plan --mode incremental
   ```
4. 再部署：
   ```bash
    mpy-cli deploy --mode incremental
   ```
5. 自动化无交互部署：
   ```bash
    mpy-cli deploy --no-interactive --yes --port <PORT>
   ```

# Interactive Behavior
- `mpy-cli init` 默认进入交互式配置向导，并可扫描端口后选择设备
- `mpy-cli config` 进入交互式配置向导，更新 `.mpy-cli.toml`
- 在 `plan/deploy` 交互模式下，若未传 `--port`，会自动扫描可用端口并提示选择
- `upload` 交互模式下，若未传 `--remote`，默认优先推导为“相对 `source_dir` 的路径”；若本地文件不在 `source_dir` 下，则回退为本地输入路径

# Quick Commands
```bash
mpy-cli init [-f|--force] [-n|--no-interactive]
mpy-cli config
mpy-cli list [-w|--workers N] [-t|--probe-timeout SECONDS] [-s|--scan-mode MODE] [-r|--reset]
mpy-cli plan [-m|--mode {incremental,full}] [-b|--base BASE] [-p|--port PORT] [-n|--no-interactive] [-y|--yes]
mpy-cli deploy [-m|--mode {incremental,full}] [-b|--base BASE] [-p|--port PORT] [-n|--no-interactive] [-y|--yes]
mpy-cli upload [-l|--local LOCAL] [-r|--remote REMOTE] [-p|--port PORT] [-n|--no-interactive] [-y|--yes]
mpy-cli run [-f|--path PATH] [-p|--port PORT] [-n|--no-interactive] [-y|--yes]
mpy-cli delete [-f|--path PATH] [-p|--port PORT] [-n|--no-interactive] [-y|--yes]
mpy-cli tree [-a|--path PATH] [-p|--port PORT] [-n|--no-interactive]
```

# Command Notes
- `init`：`--no-interactive` 跳过初始化后的交互配置向导；`--force` 覆盖已有 `.mpy-cli.toml` 与 `.mpyignore`
- `config`：无额外参数，直接进入交互式配置向导
- `list`：默认 `--workers 8`、`--probe-timeout 1.0`、`--scan-mode known-first`；`--scan-mode` 支持 `known-first`、`known-only`、`full-only`；`--reset` 会先清空扫描记录再重新扫描
- `plan`：无交互模式下应通过 `--port` 或配置文件提供端口；`--yes` 仅保留参数位，不触发写入确认；常用于部署前核对计划
- `deploy`：无交互模式下应通过 `--port` 或配置文件提供端口；未传 `--base` 时，`incremental` 默认对比 `HEAD` 与当前工作区；`--yes` 会跳过执行前确认，包括 `full` 模式二次确认
- `upload`：无交互模式下必须显式提供 `--local` 与 `--remote`；`--yes` 会跳过执行前确认
- `run/delete`：无交互模式下必须显式提供 `--path`；`--yes` 会跳过执行前确认
- `tree`：无交互模式下需通过 `--port` 或配置文件提供端口

# Cross-Project Install
- 在其他项目中推荐安装到该项目自己的虚拟环境：
  ```bash
  cd <TARGET_PROJECT_PATH>
  python3 -m venv .venv
  source .venv/bin/activate
  python3 -m pip install <SOURCE_MPY_CLI_PATH>
  ```
- 若希望本地源码修改后立即生效，改用：
  ```bash
  python3 -m pip install -e <SOURCE_MPY_CLI_PATH>
  ```
- 安装后常用命令：`mpy-cli -h`、`init`、`config`、`list`、`plan`、`deploy`、`upload`、`run`、`delete`、`tree`

# Safety Checklist
- 不确定端口时先跑 `mpy-cli list`
- 执行 `deploy` 前先跑 `plan`
- `full` 模式前确认目标设备、串口和 `device_upload_dir`
- 串口被占用时先关闭 Thonny 等工具
- 无交互模式下显式传入 `--port` 与关键参数
- 需要基于某次提交做增量比对时，显式传入 `--base`

# Troubleshooting
- `mpremote` 未安装：`python3 -m pip install mpremote`
- 串口连接失败：检查端口号并关闭占用串口的软件
- 不确定可用设备或扫描结果不稳定：先运行 `mpy-cli list`，必要时调整 `--workers`、`--probe-timeout`、`--scan-mode`
- 不确定同步范围：先运行 `mpy-cli plan ...` 再执行 `deploy`
- 不知道串口号：可查看 Thonny 中设备串口号，或直接执行 `mpy-cli list`

# Deliverables
- 可复现的部署命令（含模式与端口；若端口来自自动发现则说明依据）
- 若走增量模式，说明是否使用 `--base` 以及比对基准
- 与 `source_dir` 一致的远端路径映射
- 计划输出与实际部署行为一致
- 对 `full` 模式或路径操作的边界说明清晰
