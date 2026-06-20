# Suggested Commands

- 安装测试依赖: `uv sync --group test`
- 运行主机侧核心测试: `uv run --group test python -m pytest tests/unit tests/contract/serial_protocol -q`
- 安装板端工具: `uv sync --group board`
- 未知板端串口时先做设备发现, 再执行上传、部署或观察。
- 查看板端部署计划: `uv run --group board mpy-cli plan`
- 板端构建入口: `bash build.sh`
- 项目文件搜索优先用 `rg` 与 `rg --files`。
- Serena memory 检查: 从项目根目录运行 `serena memories check`。
- Git 提交前必须先向用户确认提交信息; 不自行 commit。
