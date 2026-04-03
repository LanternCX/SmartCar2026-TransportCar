# mpy-cli 排障入口

- 正文唯一落点：`references/mpy-cli-manual.md`
- 端口识别不清、串口号未知、连接失败：先看手册 `## 快速开始` 的第 7 步和 `## 常见问题`，优先执行 `mpy-cli list`
- 扫描模式或扫描结果异常：看手册 `## CLI 参数总览` 里的 `mpy-cli list` 章节，重点核对 `--scan-mode`、`--workers`、`--probe-timeout`、`--reset`
- 实际写入前的安全检查：先看手册 `## 快速开始` 的第 7 步和第 8 步，再回 `mpy-cli plan`、`mpy-cli deploy` 章节确认本次会写什么、会写到哪里
- 路径映射、上传范围、运行路径不符合预期：看手册 `## CLI 参数总览` 里的 `mpy-cli config`、`mpy-cli upload`、`mpy-cli run`、`mpy-cli delete`、`mpy-cli tree`，重点核对 `source_dir`、`device_upload_dir`、`.mpyignore`
