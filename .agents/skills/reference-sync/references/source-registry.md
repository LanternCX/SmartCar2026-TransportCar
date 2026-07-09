# 来源登记

## 使用说明

- 本页只登记来源、正式落点和同步触发条件，不承接正式正文。
- 正式正文由对应 Skill、开发文档或外部仓库维护；外部题面资料只维护链接入口。
- 更新正式正文或外部链接入口时，必须同步复核本页与 `maintenance-checklist.md`。

## 来源登记表

| 文档名称 | 来源 | 正式落点 | 更新时机或同步触发条件 |
| --- | --- | --- | --- |
| `mpy-cli` 正式文档 | `@../mpy-cli-dev` 仓库中的 `README.md`、`docs/developer-guide.md`、`mpy_cli/` 与 `tests/` | `@../mpy-cli-dev` | `mpy-cli` 命令、参数、路径约定、无交互流程、编译行为或排障结论变化时 |
| 串口通信协议约束 | 设备通信协议约定与仓库内实现 | `docs/developer/protocol.md` | 链路约定、协议设计取舍或硬件连接约束变化时 |
| `wireless_uart` 参考入口 | `https://gitee.com/seekfree/Wireless_Uart_Product` 与说明书 `https://gitee.com/seekfree/Wireless_Uart_Product/blob/master/%E3%80%90%E6%96%87%E6%A1%A3%E3%80%91%E8%AF%B4%E6%98%8E%E4%B9%A6%20%E8%8A%AF%E7%89%87%E6%89%8B%E5%86%8C%E7%AD%89/%E9%80%90%E9%A3%9E%E7%A7%91%E6%8A%80%20%E6%97%A0%E7%BA%BF%E8%BD%ACUSB_%E4%B8%B2%E5%8F%A3%E8%AF%B4%E6%98%8E%E4%B9%A6%20V2.3.pdf` | `docs/reference/wireless_uart/README.md` | 来源链接或无线串口使用边界变化时 |
| `problem_statement` 外部链接入口 | 官方规则页、细则页、镜像页与问答页 | `docs/problem_statement/README.md` | 题面入口链接、镜像链接或外部阅读规则变化时 |
