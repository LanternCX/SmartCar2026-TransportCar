# mpy-cli

`mpy-cli` 是一个面向 MicroPython 的交互式部署工具，用于将本地代码上传到 MicroPython 端。

支持能力：

- 增量部署（基于 `git diff` 文件集，仅上传修改部分）
- 全量部署（清空设备文件根目录后重刷）
- `.mpyignore` 忽略规则，类似 `.gitignore`
- 萌新以及跨平台友好的交互式命令行操作

---

## Quick Start

如果你是第一次使用本项目，可以遵循以下步骤。

阅读完本章之后，建议继续阅读 [在其他项目中安装为命令行工具](#install)

### 0) 环境要求

- Python 版本：`>= 3.10`（推荐 `3.11`）
- 已安装 Git
- 开发机可访问 MicroPython 设备串口

可先检查 Python 版本：

```bash
python3 --version
```

### 1) 克隆仓库

```bash
git clone https://github.com/LanternCX/mpy-cli.git
cd mpy-cli
```

### 2) 创建并激活虚拟环境

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) 安装依赖

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev]"
```

### 4) 运行测试

```bash
python3 -m pytest -q
```

### 5) 初始化项目

```bash
mpy-cli init
```

`init` 会进入交互式配置向导（可扫描设备端口并选择），无需手动编辑配置文件。

在 `plan/deploy` 交互模式下，如果未提供 `--port`，会自动扫描可用端口并提示选择。

初始化后会生成：

- `.mpy-cli.toml`
- `.mpyignore`
- `.mpy-cli/`（运行目录）

详细参数参见[CLI 参数总览](#cli-params)

### 6) 后续重配（可选）

如果你后续想修改端口、同步模式、运行目录、设备上传目录等配置，直接执行：

```bash
mpy-cli config
```

详细参数参见[CLI 参数总览](#cli-params)

### 7) 计划部署

预览部署操作，防止程序产生意料之外的行为

```bash
mpy-cli plan
```

详细参数参见[CLI 参数总览](#cli-params)

### 8) 部署到 MicroPython 端

预览部署操作，防止程序产生意料之外的行为

```bash
mpy-cli deploy
```

详细参数参见[CLI 参数总览](#cli-params)

如果后续想要进行无交互式的部署，可以执行

```bash
mpy-cli deploy --no-interactive --yes
```

---

<span id="install"></span>
## 在其他项目中安装为命令行工具

如果你要把 `mpy-cli` 安装到另一个项目里使用，推荐在该项目自己的虚拟环境中安装：

- `TARGET_PROJECT_PATH`: 你要安装并使用 mpy-cli 的目标项目目录
- `SOURCE_MPY_CLI_PATH`: 本地 mpy-cli 源码仓库路径（作为安装源）

```bash
cd <TARGET_PROJECT_PATH>
python3 -m venv .venv
source .venv/bin/activate

# 安装本地 mpy-cli 包
python3 -m pip install <SOURCE_MPY_CLI_PATH>
```

安装后可直接在该项目环境中使用：

```bash
mpy-cli -h
mpy-cli init
mpy-cli config
mpy-cli plan
mpy-cli deploy
mpy-cli upload
mpy-cli run
mpy-cli delete
mpy-cli tree
```

说明：

- 上面是“普通安装”（固定当前代码版本）。
- 如果你希望 `mpy-cli` 代码改动后立即生效，可改用可编辑安装：

```bash
python3 -m pip install -e <SOURCE_MPY_CLI_PATH>
```

---

<span id="cli-params"></span>
## CLI 参数总览

下面列出当前可用命令和参数，便于查阅。

### `mpy-cli init`

```bash
mpy-cli init [--force] [--no-interactive]
```

- `--force`：覆盖已有 `.mpy-cli.toml` 和 `.mpyignore`。
- `--no-interactive`：跳过初始化后的交互配置向导。

### `mpy-cli config`

```bash
mpy-cli config
```

- 无额外参数。
- 进入交互式配置向导，更新 `.mpy-cli.toml`。

常用配置项说明：

- `source_dir`：本地源码根目录。`plan/deploy` 计算远端路径时以该目录为根，不保留 `source_dir` 前缀。
- `.mpyignore`：规则匹配对象为“相对 `source_dir` 的路径”。
- 当 `source_dir = "src"` 时，本地 `src/main.py` 对应远端 `:main.py`。
- 若历史 `.mpyignore` 规则包含 `src/...` 前缀，需迁移为相对 `source_dir` 的写法。
- `device_upload_dir`：设备端上传目录前缀，留空表示设备根目录。
- 当 `device_upload_dir = "apps/demo"` 时，本地 `main.py` 会上传到设备 `:apps/demo/main.py`。
- `full` 模式会清空该上传目录，而不是整机设备根目录。

### `mpy-cli plan`

```bash
mpy-cli plan [--mode {incremental,full}] [--port PORT] [--no-interactive] [--yes]
```

- `--mode`：指定同步模式（`incremental` 或 `full`）。
- `--port`：指定设备端口（如 `/dev/ttyACM0` 或 `COM3`）。
- `--no-interactive`：禁用交互提问。
- `--yes`：保留参数；在 `plan` 中不会触发写入确认流程。

### `mpy-cli deploy`

```bash
mpy-cli deploy [--mode {incremental,full}] [--port PORT] [--no-interactive] [--yes]
```

- `--mode`：指定同步模式（`incremental` 或 `full`）。
- `--port`：指定设备端口。
- `--no-interactive`：禁用交互提问。
- `--yes`：跳过执行前确认（包括全量模式二次确认）。

推荐用法：

```bash
mpy-cli deploy --no-interactive --yes
```

进行 `config` 之后直接无交互烧入

### `mpy-cli upload`

```bash
mpy-cli upload [--local LOCAL] [--remote REMOTE] [--port PORT] [--no-interactive] [--yes]
```

- `--local`：本地文件路径（如 `seekfree_demo/E01_demo.py`）。
- `--remote`：设备目标路径；不传时交互模式默认优先使用“相对 `source_dir` 路径”，若本地文件不在 `source_dir` 下则回退为本地输入路径，可手动修改。
- `--port`：指定设备端口。
- `--no-interactive`：禁用交互提问；此时需显式提供 `--local` 和 `--remote`。
- `--yes`：跳过执行前确认。

推荐用法：

```bash
mpy-cli upload --local <LOCAL>
```

填写字段 `LOCAL` 指定本地文件路径之后交互式确认远程路径

### `mpy-cli run`

```bash
mpy-cli run [--path PATH] [--port PORT] [--no-interactive] [--yes]
```

- `--path`：设备目标文件路径，语义为相对 `device_upload_dir`。
- `--port`：指定设备端口。
- `--no-interactive`：禁用交互提问；此时需显式提供 `--path`。
- `--yes`：跳过执行前确认。

推荐用法：

```bash
mpy-cli run --path main.py
```

若配置 `device_upload_dir = "apps/demo"`，则会执行 `:apps/demo/main.py`。

### `mpy-cli delete`

```bash
mpy-cli delete [--path PATH] [--port PORT] [--no-interactive] [--yes]
```

- `--path`：设备目标路径，语义为相对 `device_upload_dir`，可为文件或目录。
- `--port`：指定设备端口。
- `--no-interactive`：禁用交互提问；此时需显式提供 `--path`。
- `--yes`：跳过执行前确认。

推荐用法：

```bash
mpy-cli delete --path obsolete.py
```

若配置 `device_upload_dir = "apps/demo"`，则会删除 `:apps/demo/obsolete.py`。
当 `--path` 指向目录时，默认递归删除整个目录。

### `mpy-cli tree`

```bash
mpy-cli tree [--path PATH] [--port PORT] [--no-interactive]
```

- `--path`：设备目标目录路径，语义为相对 `device_upload_dir`；不传时默认读取 `device_upload_dir` 根目录。
- `--port`：指定设备端口。
- `--no-interactive`：禁用交互提问；此时需通过 `--port` 或配置文件提供端口。

推荐用法：

```bash
mpy-cli tree --path .
```

若配置 `device_upload_dir = "apps/demo"`，则默认读取 `:apps/demo`；例如 `--path services` 会读取 `:apps/demo/services`。

---

## 常见问题

### 1) `mpremote` 找不到

```bash
python3 -m pip install mpremote
```

### 2) 串口连接失败或者烧录报错

- 检查串口号（如 `/dev/ttyACM0`、`COM3`）
- 关闭占用串口的软件（如 Thonny）

### 3) 我不确定会同步哪些文件

先执行 `mpy-cli plan ...` 查看计划，再执行 `deploy`。

### 4) 我不知道串口号

参见 Thonny 中的设备串口号（圆括号内的内容）。

### 5) 为什么选择 mpy-cli？

搭配 stubs，例如在智能车竞赛中使用我的项目[micropython-smartcar-stubs](https://github.com/LanternCX/micropython-smartcar-stubs)。

可以实现完全无 thonny 开发 MicroPython 项目。

---

## Contribute

开发与规范说明：`docs/developer-guide.md`

本仓库采用 GPL-3.0 协议开源，如果用于竞赛目的可酌情在赛后遵守协议。

欢迎 Issue / PR / Star。
