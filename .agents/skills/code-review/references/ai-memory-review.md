# AI 内存自检入口

## 定位

- 内存检查默认由 AI 执行, 不作为用户人工 review 负担
- 对共享底盘执行内核、运行时 owner、诊断面和板端探针的改动, 收口第一优先级是最小内存占用指标, 不是结构整洁度
- MicroPython 不是普通 CPython 环境, 内存 review 必须按 MicroPython RAM、heap、qstr、对象模型和 GC 行为判断

## 依据入口

- MicroPython 受限环境写法: https://docs.micropython.org/en/latest/reference/constrained.html
- MicroPython 对象与 heap 模型: https://docs.micropython.org/en/latest/develop/memorymgt.html
- MicroPython 文档和源码优先级高于普通 Python 经验; 无法仅靠文档判断时, 以板端实测和仓库 memory 结论校准

## 必查项

- 新增常驻对象时, 必须说明 owner、阶段、分类、触发条件和必要性
- 模块级可变运行时全局状态属于阻断项
- 可延迟功能若被重新放回构造期无条件初始化, 直接视为不通过
- 热路径新增大字符串拼接、大临时容器、字符串键字典或无解释动态分配时, 必须证明必要性
- 角色运行时、协议层和控制热路径新增 qstr 压力时, 必须证明该字符串字段、来源标签、状态名或日志文本属于正式运行必要信息
- 固定字段状态从 dict 改成 class 或 if-else 不等于 qstr 优化; 优先审查短名、`const` 整数、固定索引 tuple/list、`bytes`、预分配 buffer 和直接过程逻辑
- class 可以提高可读性, 但对象字段名同样会形成 qstr 压力; 不能把对象化本身当作内存优化结论
- 诊断面新增同步细日志、事件细日志、速度来源文本、快照字典、长期诊断计数或测试便利入口时, 默认不通过
- 拆模块只有在减少默认导入集或延迟非主路径能力时才算内存优化; 单纯拆文件不作为通过理由
- 结构更清晰但内存指标未改善, 不算有效重构

## 留证要求

- 必须给出关键内存证据, 至少覆盖 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle` 和 `diag_survival`
- verbose `mem_info` 或等价观测前必须先执行 GC, 否则不得作为常驻占用结论
- GC 前后内存差异需要分开记录; GC 自身主要作为性能开销评估, 不作为常驻内存大头
- 临时内存探针不得进入最终提交; 提交内容只保留最小且必要的观测口
- review 结论必须明确新增常驻对象为何属于应该保留的类型, 而不是可延后或可删除的负担
