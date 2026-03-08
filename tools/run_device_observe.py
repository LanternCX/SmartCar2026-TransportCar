"""Stage 3 人工调试提示脚本."""

MESSAGE = """Stage 3 已调整为 uart3 人工调试流程，不再提供自动观测脚本。

自动化裸片 smoke 请使用：
  python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101

Stage 3 建议流程：
  1. 保持 OpenArt 继续连接 uart6
  2. 将调试串口接到 uart3
  3. 人工发送 ?health/?tick/?imu/?enc/?motor/?vision/?lock/?pos 并观察回包
  4. 结合现场现象，由 AI 协助归因逻辑问题
"""


def main(argv=None):
    """命令行入口."""
    del argv
    print(MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
