# 搬运车内存评审门禁

## 目的

本说明用于约束 `TransportCar` 及其相关运行时改动的 code review。评审的一号目标不是“结构更清晰”, 而是“最小内存占用指标是否达标”。

## 强制门禁

- review 必须先看板端内存证据, 再讨论结构整洁度
- 任何新增常驻对象都必须标注 A / B / C / D / E 类
- `import-time` 禁止自动发现, 自动注册, 目录扫描和重型单例初始化
- 模块级可变运行时全局属于阻断项
- 可延迟功能若被放回构造期无条件初始化, 直接判定不通过
- 若 `mem_free_after_import`、`mem_free_after_core_init`、`mem_free_after_feature_init`、`mem_free_runtime_idle` 任一指标变差且没有必要性证明, 直接判定不通过
- 若低内存下 `?health`、`?tick`、`?vision` 不能保活, 直接判定不通过

## 必答问题

每次评审都必须明确回答:

1. 新增了哪些常驻对象?
2. 它们为什么必须属于 A / B 类, 而不是 C / D 类?
3. 是否引入了新的重复 owner, 重复缓存或隐式共享协议?
4. 板端 `mem_free` 指标相较基线是否变好, 持平还是变差?
5. 最小诊断面是否仍然存活?

## 证据格式

评审结论至少应附带:

- `mem_free_after_import`
- `mem_free_after_core_init`
- `mem_free_after_feature_init`
- `mem_free_runtime_idle`
- `diag_survival`
- 使用的 probe / smoke 命令

## 阻断示例

- 仅凭“文件更小了”就声称重构完成
- 引入新的 `services` 层 God object 或 facade 缓存第二份状态
- 为了 review 好看而增加空抽象, 但常驻内存没有下降
- 在热路径新增大字符串拼接, 大临时容器或不可解释的动态分配

## 结论要求

最终 review 输出必须直接回答: 当前改动是否满足最小内存占用指标。如果不能明确回答, 视为证据不足, 不得通过。
