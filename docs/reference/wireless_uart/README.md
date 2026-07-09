# 无线串口参考入口

本目录只保留逐飞无线转 USB / 串口模块的来源链接和项目使用边界, 不维护说明书正文或配图镜像。

## 外部来源

- 原始项目: [Wireless_Uart_Product](https://gitee.com/seekfree/Wireless_Uart_Product)
- 原始说明书: [逐飞科技 无线转USB_串口说明书 V2.3](https://gitee.com/seekfree/Wireless_Uart_Product/blob/master/%E3%80%90%E6%96%87%E6%A1%A3%E3%80%91%E8%AF%B4%E6%98%8E%E4%B9%A6%20%E8%8A%AF%E7%89%87%E6%89%8B%E5%86%8C%E7%AD%89/%E9%80%90%E9%A3%9E%E7%A7%91%E6%8A%80%20%E6%97%A0%E7%BA%BF%E8%BD%ACUSB_%E4%B8%B2%E5%8F%A3%E8%AF%B4%E6%98%8E%E4%B9%A6%20V2.3.pdf)

## 项目使用边界

- 规则事实以外部说明书为准, 使用前重新核对来源。
- 本仓库正式主辅通信使用 `UART8` 直连, 不是无线串口主链路。
- 无线串口只作为现场测试、排障或备用链路资料入口。
- 需要无线串口板端验证时, 以 `seekfree_demo/` 中对应示例和当前硬件接线为准。
