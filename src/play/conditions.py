"""Play 条件回调。"""


def yellow_line_ready(ctx):
    return bool(ctx.yellow_line_ready())
