# 2026 智能车蚂蚁搬家组浙江赛区-想吃雪糕：代码仓库

对牛方案，省赛预赛 35s 完赛，决赛 87s 完赛。重量罚时在 10s 左右。

演示视频：[Bilibili](https://www.bilibili.com/video/BV1fuKv6yE4k)

浅析文章：

- 我的博客：[https://www.caoxin.xyz/blog/smart-car-2026](https://www.caoxin.xyz/blog/smart-car-2026)
- 知乎：[https://zhuanlan.zhihu.com/p/2071741059273695593](https://zhuanlan.zhihu.com/p/2071741059273695593)
- Github: [LanternCX/Blogs](https://github.com/LanternCX/Blogs/blob/main/Robotic/2026%20Smart%20Car%20Race%20Editorial/main.md)

浙江省赛只比了决赛。这个决赛成绩在全国的区赛应该都能排到比较靠前的位置（华北赛区排名第一、东北赛区排名第二、华南赛区排名第三、西部赛区排名第三、华东赛区赛题和我们不一样无法比较），但是在浙江只拿到了省第五、学校第三。由于赛区政策原因，很遗憾只获得了省三，并且差一名进国。

整理了一下资料将我们的工作开源出来，希望能够给后来的智能车任务组、NXP-MicroPython 组的同学带来一些启发。

---

实际上，由于代码 AI 率在 95% 以上，我认为我的代码写的并不算优秀，而且我并没有十分追求代码的工整。

因此，我并不推荐你直接阅读我的代码仓库，取而代之的是阅读上面的浅析文章，并让 AI 读一下代码仓库，然后亲自阅读一些你感兴趣的有意思的代码片段。

不过，仓库中的每一个 PR 我都有仔细认真的撰写。如果你想阅读并获得更多的调试经验，可以看看我写的 PR。同时，我也会在文章中引用几个 PR 来说明我们是如何解决问题的。

感谢蚂蚁搬家群中和我交流的、来自华北赛区、东北赛区、西部赛区、华东赛区、华南赛区、新疆赛区、安徽赛区、浙江赛区的各位佬们，这套方案的形成离不开我和来自全国各地的佬们的交流。

---

项目开源链接：

- 主仓库：[LanternCX/SmartCar2026-TransportCar](https://github.com/LanternCX/SmartCar2026-TransportCar)
- 视觉仓库：[LanternCX/SmartCar2026-Vision](https://github.com/LanternCX/SmartCar2026-Vision)
- 简陋的调试上位机：[LanternCX/SmartCar2026-Controller](https://github.com/LanternCX/SmartCar2026-Controller)
- 硬件：[https://github.com/LanternCX/SmartCar2026-TransportCar/releases](https://github.com/LanternCX/SmartCar2026-TransportCar/releases/tag/v5.0.0)

感兴趣也可以参与我正在维护的：

- [LanternCX/mpy-cli: mpy-cli | 轻量、便捷、灵活地完成 micro-python 代码部署](https://github.com/LanternCX/mpy-cli)
- [LanternCX/micropython-smartcar-stubs: 逐飞 mpy 库 stubs，用于解决 VS Code 开发 micro-python 智能车的问题](https://github.com/LanternCX/micropython-smartcar-stubs)
- [LanternCX/ChromaForge: 🎨 ChromaForge | 面向计算机视觉工作流的颜色规则标定桌面软件](https://github.com/LanternCX/ChromaForge)

如果我们的工作有帮助，欢迎到点 Star 支持。

如果本开源对你有启发，也欢迎开源自己的作品，一同共建生态。
