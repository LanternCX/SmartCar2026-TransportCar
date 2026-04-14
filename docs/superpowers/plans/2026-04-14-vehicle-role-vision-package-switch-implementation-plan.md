# 车号识别驱动的主辅车视觉包切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重构当前大文件与不引入全局共享可变状态的前提下, 让运行时先识别车号, 再切换主车或辅车的视觉包, 为后续辅车视觉校准与主车速度前馈留出稳定边界。

**Architecture:** 保持当前单仓库与共享底座不变, 只在正常运行入口之后新增一层很薄的角色视觉包分流边界。车号识别模块先解码 `D8/D9`, 再由运行入口按角色切到 `src/vision/master/` 或 `src/vision/assistant/`; `TransportCar` 保持当前内部结构不动, 不在本轮做结构性拆分。

**Tech Stack:** Python, MicroPython 兼容运行时代码, pytest unit/contract tests, 现有 `main.py` + `script/remote_control.py` 板端入口链路

---

## 文件结构与职责

- Create: `src/vision/vehicle_role.py`
  负责 `D8/D9` 角色输入读取、组合解码与异常组合拒绝, 不导入任何重运行时对象。

- Create: `src/vision/__init__.py`
  提供按角色创建当前视觉包入口的唯一装配入口, 通过分支内局部导入避免同时拉起主车和辅车两套包。

- Create: `src/vision/master/__init__.py`
  暴露主车视觉包当前入口。

- Create: `src/vision/master/runtime.py`
  承接当前主车视觉运行入口, 当前阶段先保持主车运行链可由角色分流进入。

- Create: `src/vision/assistant/__init__.py`
  暴露辅车视觉包当前入口。

- Create: `src/vision/assistant/runtime.py`
  承接当前辅车视觉运行入口, 当前阶段先保持辅车运行链可由角色分流进入, 不展开完整融合算法。

- Modify: `src/script/remote_control.py`
  改成薄启动壳: 先识别车号, 再走 `src/vision/` 下对应角色入口, 不在模块导入期直接创建大对象。

- Create: `tests/unit/test_vehicle_role.py`
  锁定 `src/vision/vehicle_role.py` 的 `D8/D9` 组合解码、异常组合与引脚读取行为。

- Create: `tests/unit/test_role_vision_layer_factory.py`
  锁定角色到视觉包的装配关系, 避免同时导入两套包。

- Create: `tests/unit/test_remote_control_role_dispatch.py`
  锁定 `remote_control.py` 的薄启动壳职责: 先识别角色, 再切到 `src/vision/` 对应入口, 再启动运行时。

- Modify: `docs/developer/vision.md`
  同步正式文档口径, 明确当前运行时通过车号切换主车或辅车视觉包。

### Task 1: 固化车号识别边界

**Files:**
- Create: `src/vision/vehicle_role.py`
- Create: `tests/unit/test_vehicle_role.py`

- [ ] **Step 1: 写失败测试, 锁定角色组合语义**

在 `tests/unit/test_vehicle_role.py` 新增三组断言:

1. `decode_vehicle_role(0, 1)` 返回主车角色。
2. `decode_vehicle_role(1, 0)` 返回辅车角色。
3. `decode_vehicle_role(0, 0)` 与 `decode_vehicle_role(1, 1)` 都抛出异常, 明确其余组合是非法组合。

同时增加一组读取测试, 锁定角色读取会用 `D8` 与 `D9`, 并使用上拉输入模式。

- [ ] **Step 2: 运行测试确认失败**

运行 `python3 -m pytest tests/unit/test_vehicle_role.py -q`。

预期: 失败, 原因是 `vehicle_role` 模块尚不存在, 或角色解码函数尚未实现。

- [ ] **Step 3: 实现最小车号识别模块**

在 `src/vision/vehicle_role.py` 中实现以下内容:

1. 主车与辅车角色常量。
2. 纯组合解码函数, 只负责把 `D8/D9` 电平转换成角色或异常。
3. 读取引脚并调用解码函数的板端入口。

实现要求:

1. 只依赖 `machine.Pin` 这类板端最小能力。
2. 不导入 `TransportCar`、视觉层或其他重运行时模块。
3. 角色异常必须显式抛出, 不做静默兜底。

- [ ] **Step 4: 重新运行测试确认通过**

运行 `python3 -m pytest tests/unit/test_vehicle_role.py -q`。

预期: 全绿。

- [ ] **Step 5: 提交检查点**

本任务完成后, 如果需要创建提交, 先向用户确认提交消息, 不直接提交。

### Task 2: 建立角色视觉包装配入口

**Files:**
- Create: `src/vision/__init__.py`
- Create: `src/vision/master/__init__.py`
- Create: `src/vision/master/runtime.py`
- Create: `src/vision/assistant/__init__.py`
- Create: `src/vision/assistant/runtime.py`
- Create: `tests/unit/test_role_vision_layer_factory.py`

- [ ] **Step 1: 写失败测试, 锁定角色到视觉包的装配关系**

在 `tests/unit/test_role_vision_layer_factory.py` 新增以下断言:

1. 主车角色创建主车视觉包入口。
2. 辅车角色创建辅车视觉包入口。
3. 未知角色会被拒绝。
4. 装配入口通过分支内导入创建对象, 不在模块导入期同时拉起两套层。

最后一条不要通过正则卡死源码细节, 而是通过 monkeypatch 或导入探针验证“只会走被选中的那一支”。

- [ ] **Step 2: 运行测试确认失败**

运行 `python3 -m pytest tests/unit/test_role_vision_layer_factory.py -q`。

预期: 失败, 原因是 `src/vision/master/` 与 `src/vision/assistant/` 包结构尚未建立。

- [ ] **Step 3: 实现装配入口与两套最小视觉包**

实现要求:

1. `src/vision/__init__.py` 只暴露一个按角色创建当前视觉包入口的入口。
2. `src/vision/master/` 作为主车视觉包当前入口。
3. `src/vision/assistant/` 作为辅车视觉包当前入口。
4. 本轮不把角色差异继续塞回 `TransportCar` 内部。

- [ ] **Step 4: 重新运行测试确认通过**

运行 `python3 -m pytest tests/unit/test_role_vision_layer_factory.py -q`。

预期: 全绿。

- [ ] **Step 5: 提交检查点**

本任务完成后, 如果需要创建提交, 先向用户确认提交消息, 不直接提交。

### Task 3: 把 `remote_control.py` 收口为角色分流启动壳

**Files:**
- Modify: `src/script/remote_control.py`
- Create: `tests/unit/test_remote_control_role_dispatch.py`

- [ ] **Step 1: 写失败测试, 锁定启动壳职责**

在 `tests/unit/test_remote_control_role_dispatch.py` 中通过按文件路径加载模块并 monkeypatch helper 的方式锁定以下行为:

1. 启动时先读取车号。
2. 根据角色切到 `src/vision/master/` 或 `src/vision/assistant/` 对应包。
3. 然后才启动 ticker 与主循环。
4. 模块导入期不应直接创建运行时对象。

- [ ] **Step 2: 运行测试确认失败**

运行 `python3 -m pytest tests/unit/test_remote_control_role_dispatch.py -q`。

预期: 失败, 原因是当前 `remote_control.py` 仍在模块导入期直接创建 `TransportCar` 并启动主循环。

- [ ] **Step 3: 实现薄启动壳**

实现要求:

1. `remote_control.py` 先读取角色, 再进入 `src/vision/master/` 或 `src/vision/assistant/` 对应包, 再创建当前运行链对象。
2. 运行入口保持板端可执行, 不破坏现有 `main.py -> execfile(script/remote_control.py)` 链路。
3. `remote_control.py` 只承担启动分流职责, 不顺手吸收主车或辅车的具体视觉逻辑。
4. 日志保留足够的启动阶段信息, 便于定位卡在角色识别、视觉层装配还是运行时创建。

- [ ] **Step 4: 重新运行相关测试确认通过**

依次运行:

1. `python3 -m pytest tests/unit/test_remote_control_role_dispatch.py -q`
2. `python3 -m pytest tests/unit/test_main_entry.py -q`

预期: 全绿, 且 `main.py` 仍保持不直接读取 `D8/D9` 的边界。

- [ ] **Step 5: 提交检查点**

本任务完成后, 如果需要创建提交, 先向用户确认提交消息, 不直接提交。

### Task 4: 同步正式文档口径并做最小联验

**Files:**
- Modify: `docs/developer/vision.md`

- [ ] **Step 1: 更新正式文档口径**

把正式文档同步到当前实现边界:

1. 运行时会先识别车号。
2. 角色识别用于切换主车或辅车视觉包。
3. 本轮只建立辅车视觉校准与主车速度前馈的承接边界, 不把完整融合算法写成既成事实。

文档只写当前代码与设计已经确认的事实, 不写历史性表述。

- [ ] **Step 2: 运行最小自动验证**

运行 `python3 -m pytest tests/unit/test_vehicle_role.py tests/unit/test_role_vision_layer_factory.py tests/unit/test_remote_control_role_dispatch.py tests/unit/test_main_entry.py tests/contract/test_non_query_command_reply_contract.py -q`。

预期: 全绿。

- [ ] **Step 3: 记录板端确认清单**

实现完成后, 通过对话记录最小板端确认项:

1. 主车组合 `01` 能进入 `vision/master/`。
2. 辅车组合 `10` 能进入 `vision/assistant/`。
3. 非法组合会拒绝继续进入正常运行链。
4. `main.py` 仍只负责按钮脚本分发。

- [ ] **Step 4: 提交检查点**

本任务完成后, 如果需要创建提交, 先向用户确认提交消息, 不直接提交。

## 计划自检

- Spec coverage: 本计划覆盖了 spec 中的全部硬要求: 车号解码、角色视觉包装配边界、主/辅两包最小入口、字符串协议与车内控制量边界、避免继续把角色逻辑堆进当前大文件。
- Placeholder scan: 计划没有使用 TBD、TODO、后续补充等占位语句, 每个任务都给出了明确文件、测试入口与完成条件。
- Type consistency: 计划统一使用“车号识别模块”“角色视觉包”“薄启动壳”这几组名称, 未在不同任务中切换为不同含义的命名。
