# mpy-cli 参考入口

## 正式来源

- 工具仓库：`@../mpy-cli-dev`
- 命令总览、安装方式、参数说明、无交互调用：`@../mpy-cli-dev/README.md`
- 运行目录、配置文件与工程边界：`@../mpy-cli-dev/docs/developer-guide.md`
- 实际行为、边界细节与回归依据：`@../mpy-cli-dev/mpy_cli/` 与 `@../mpy-cli-dev/tests/`

## 命令与路径边界

- 命令总览与参数说明优先查 `README.md`
- `source_dir`、`device_upload_dir`、`.mpyignore`、上传范围与编译开关边界优先查 `README.md` 中的 `config`、`plan`、`deploy`、`upload`、`run`、`delete`、`tree` 章节
- 运行目录、配置文件与工程边界查 `docs/developer-guide.md`
- 部署前默认先执行 `mpy-cli list` 与 `mpy-cli plan`

## 排障路径

- 端口识别不清、串口号未知、连接失败：先查 `README.md` 快速开始与 `mpy-cli list` 章节，并优先执行 `mpy-cli list`
- 扫描模式或扫描结果异常：查 `mpy-cli list` 章节，重点核对 `--scan-mode`、`--workers`、`--probe-timeout`、`--reset`
- 实际写入前的安全检查：查 `mpy-cli plan`、`mpy-cli deploy` 章节，确认本次会写什么、会写到哪里
- 路径映射、上传范围、运行路径或编译结果不符合预期：查 `config`、`plan`、`deploy`、`upload`、`run`、`delete`、`tree` 章节，必要时核对 `docs/developer-guide.md`
