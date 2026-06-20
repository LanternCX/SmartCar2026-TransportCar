# Task Completion

- 默认完成检查: 按改动范围运行最小相关测试; 影响共享运行时、协议、入口或状态机时运行 `uv run --group test python -m pytest tests/unit tests/contract/serial_protocol -q`。
- 协议改动: 同步检查车端和 OpenART 视觉仓库的帧常量、CRC、接收扫描、分段到达和错位回归; 高频速度链与低频可靠链分别验证。
- 硬件相关改动: 主机测试通过不等于板端可用; 需要说明是否已做 mpy-cli plan / deploy / upload / 板端观察。
- 文档或注释改动: 检查是否重复代码事实、是否带演化口吻、是否引用不存在的入口。
- 完成前检查 `git status --short`, 不覆盖用户已有改动。
- 若要提交, 先向用户确认 commit message; commit message 不加非真人 co-author。
