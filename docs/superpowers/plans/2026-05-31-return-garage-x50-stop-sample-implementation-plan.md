# 主车回库固定列采样停车实现计划

执行状态: Archive

## 目标

按 `docs/superpowers/specs/2026-05-31-return-garage-x50-stop-sample-design.md` 将回库平移停车判据调整为 Y=160 有黄色且 X=270 连续 5 帧无黄色。

## 修改范围

- 修改: `../SmartCar2026-Vision/master/main.py`
- 修改: `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
- 修改: `../SmartCar2026-Vision/README.md`
- 修改: `docs/superpowers/memory/milestone/entries/2026-05/2026-05-31-2.md`
- 修改: `docs/superpowers/memory/milestone/INDEX.md`

## 任务

1. 调整视觉单元测试, 覆盖原始 Y 速度、丢线不完成、Y=160 无黄色不完成和 X=270 连续 5 帧无黄色完成。
2. 在 `master/main.py` 增加固定行列采样判定。
3. 让回库黄线平移段只在 Y=160 有黄色且 X=270 连续 5 帧没有黄色时回报完成事件。
4. 同步 README 和 Memory 的当前事实。
5. 运行主车仓库与视觉仓库相关测试。

## 验证命令

- 主车仓库: `uv run --group test python -m pytest tests/unit/vision tests/unit/runtime -q`
- 视觉仓库: 在 `../SmartCar2026-Vision` 下运行 `uv run --with pytest python -m pytest tests/unit tests/contract -q`
