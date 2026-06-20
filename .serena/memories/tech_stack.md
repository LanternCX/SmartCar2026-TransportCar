# Tech Stack

- 语言: Python 3.10+, 代码需兼顾 CPython 主机测试与 MicroPython / OpenART 板端运行限制。
- 包管理与命令运行: 使用 `uv`; 避免额外工具链。
- 测试依赖: `pytest` 由 `test` 依赖组提供。
- 类型检查依赖: `pyright` 由 `type` 依赖组提供, 不是每次任务默认必跑。
- 板端工具依赖: `mpy-cli`, `mpremote==1.27.0`, `mpy-cross==1.20.0` 由 `board` 依赖组提供。
- `mpy-cli` 来源为相邻本地路径 `../mpy-cli-dev`, editable。
- 板端事实: RT1021 MicroPython v1.20.0, mimxrt, `.mpy` 配置使用 `armv7emdp`。
- 低内存约束: 大量 docstring 或普通未使用字符串可能抬高板端编译期内存峰值; 低内存板端优先使用电脑侧交叉编译 `.mpy` 部署。