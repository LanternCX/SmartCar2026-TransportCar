# mpy-cli 排障入口

- 正式来源仓库：@../mpy-cli-dev
- 端口识别不清、串口号未知、连接失败：先看 `@../mpy-cli-dev/README.md` 中的快速开始与 `mpy-cli list` 章节，优先执行 `mpy-cli list`
- 扫描模式或扫描结果异常：看 `@../mpy-cli-dev/README.md` 里的 `mpy-cli list` 章节，重点核对 `--scan-mode`、`--workers`、`--probe-timeout`、`--reset`
- 实际写入前的安全检查：先看 `@../mpy-cli-dev/README.md` 里的 `mpy-cli plan`、`mpy-cli deploy` 章节，确认本次会写什么、会写到哪里
- 路径映射、上传范围、运行路径或编译结果不符合预期：看 `@../mpy-cli-dev/README.md` 里的 `mpy-cli config`、`mpy-cli plan`、`mpy-cli deploy`、`mpy-cli upload`、`mpy-cli run`、`mpy-cli delete`、`mpy-cli tree`，必要时再核对 `@../mpy-cli-dev/docs/developer-guide.md`
