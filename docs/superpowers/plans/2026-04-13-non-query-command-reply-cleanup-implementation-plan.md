# 非查询命令回包收口实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来执行本计划。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 删除当前运行时里非查询命令的主动提示回包, 同时保留查询回包和真正执行异常时的错误输出。

**Architecture:** 先用主机侧测试锁住“普通命令静默、查询保留、异常保留、`print` 静默”的边界, 再对现有提示点做最小删除, 不扩展协议结构, 不恢复旧日志系统。文档只同步当前正式主线口径, 明确 `print` 不再直接透传到运行时串口。

**Tech Stack:** Python 3.8+ 主机侧 `pytest`, RT1021 MicroPython 运行时, `src/services/transport_car.py`, `src/services/commands/`, `openart-protocol.md`

**Git Note:** 本仓库提交前必须先向你确认提交消息, 因此本计划不包含自动提交步骤。

---

## 文件边界

- Create: `tests/unit/test_non_query_command_reply.py`
- Create: `tests/contract/test_non_query_command_reply_contract.py`
- Modify: `src/services/transport_car.py:395-413`
- Modify: `src/services/transport_car.py:908-916`
- Modify: `src/services/commands/cmd_rear.py:1-20`
- Modify: `src/services/commands/cmd_print.py:1-14`
- Modify: `.agents/skills/using-rules/references/openart-protocol.md:104-145`

### Task 1: 先用主机侧测试锁住回包边界

**Files:**
- Create: `tests/unit/test_non_query_command_reply.py`
- Create: `tests/contract/test_non_query_command_reply_contract.py`

- [ ] **Step 1: 新建主机侧单元测试文件**

  在 `tests/unit/test_non_query_command_reply.py` 建立最小假上下文和串口捕获对象, 只覆盖这轮需要的 4 条行为事实:
  1. `rear` 命令仍会修改模式状态, 但不再往 `uart3` 写提示文本。
  2. `print` 命令仍可被路由接受, 但运行时不再往 `uart3` 写文本。
  3. `router.handle_query("health", ...)` 仍会产生 `?health=` 查询回包。
  4. `router.handle_query("missing", ...)` 仍会产生 `?unknown=` 查询回包。

- [ ] **Step 2: 运行单元测试并确认先失败**

  Run: `python3 -m pytest tests/unit/test_non_query_command_reply.py -q`

  Expected: FAIL, 失败原因应直接指向当前 `cmd_rear` / `cmd_print` 仍会写串口, 或查询假上下文尚未补齐。

- [ ] **Step 3: 新建最小契约测试文件**

  在 `tests/contract/test_non_query_command_reply_contract.py` 锁住不适合直接导入板端运行时的 4 条事实:
  1. `src/services/transport_car.py` 中不再保留 `RCV:` 这类普通命令回显文本。
  2. `src/services/transport_car.py` 中不再保留动作完成后的提示文本。
  3. `src/services/transport_car.py` 仍保留 `ERR` 错误输出路径。
  4. 正式协议文档不再把 `print=<text>` 描述成透传到 `UART3` 输出。

- [ ] **Step 4: 运行契约测试并确认先失败**

  Run: `python3 -m pytest tests/contract/test_non_query_command_reply_contract.py -q`

  Expected: FAIL, 失败原因应直接指向源码里仍存在旧提示文本, 或协议文档仍声明 `print` 会输出到 `UART3`。

- [ ] **Step 5: 复核测试边界**

  确认这两组测试只锁本轮边界, 不去约束无关文本、不扫描整份大文档的所有表述、也不把启动日志、`stop()` 输出或其他独立脚本打印混进本轮范围。

### Task 2: 对运行时提示点做最小收口

**Files:**
- Modify: `src/services/transport_car.py:395-413`
- Modify: `src/services/transport_car.py:908-916`
- Modify: `src/services/commands/cmd_rear.py:1-20`
- Modify: `src/services/commands/cmd_print.py:1-14`

- [ ] **Step 1: 删除普通命令回显**

  在 `src/services/transport_car.py:395-413` 删除 `uart3` 上的 `RCV:` 回显, 保持查询分发和普通命令执行流程不变。

- [ ] **Step 2: 删除动作完成提示**

  在 `src/services/transport_car.py:908-916` 删除动作完成后自动输出的提示文本, 保留原有状态回收、停车和模式恢复逻辑。

- [ ] **Step 3: 删除 `rear` 的成功提示**

  在 `src/services/commands/cmd_rear.py` 保留模式状态更新, 去掉成功切换后的 `uart3.write(...)`。

- [ ] **Step 4: 让 `print` 在运行时静默**

  在 `src/services/commands/cmd_print.py` 保留命令入口和字符串参数接受能力。若实现过程中确认当前正式主线仍有可直接复用的统一关闭入口, 就让 `print` 服从该入口; 若没有, 就直接保持运行时静默。不要为它恢复旧日志开关, 也不要新增替代调试通道。

- [ ] **Step 5: 运行第一轮回归**

  Run: `python3 -m pytest tests/unit/test_non_query_command_reply.py tests/contract/test_non_query_command_reply_contract.py -q`

  Expected: PASS, 且查询回包断言、错误输出断言和静默断言同时成立。

### Task 3: 同步正式协议文档口径

**Files:**
- Modify: `.agents/skills/using-rules/references/openart-protocol.md:104-145`
- Test: `tests/contract/test_non_query_command_reply_contract.py`

- [ ] **Step 1: 收口 `print` 的协议表述**

  将 `print=<text>` 从“透传到 RT1021 的 `UART3` 输出”改成与当前实现一致的口径: 优先服从当前正式主线里可直接复用的统一关闭入口; 若无该入口, 则运行时静默。

- [ ] **Step 2: 收口日志控制说明**

  删除“`print` 仍是原始文本透传接口”这类与当前实现不一致的描述, 改成不会误导联调者期待运行时串口输出, 且与统一关闭口径一致的表述。

- [ ] **Step 3: 再跑契约测试**

  Run: `python3 -m pytest tests/contract/test_non_query_command_reply_contract.py -q`

  Expected: PASS, 协议文档与当前实现口径一致。

### Task 4: 做完整验证并准备后续执行

**Files:**
- Test: `tests/unit/test_non_query_command_reply.py`
- Test: `tests/contract/test_non_query_command_reply_contract.py`

- [ ] **Step 1: 运行本轮目标测试集**

  Run: `python3 -m pytest tests/unit/test_non_query_command_reply.py tests/contract/test_non_query_command_reply_contract.py -q`

  Expected: PASS。

- [ ] **Step 2: 运行主机侧联合检查**

  Run: `python3 -m pytest tests/unit tests/contract -q`

  Expected: PASS, 没有因为这轮静默收口误伤现有查询、协议或命令语义。

- [ ] **Step 3: 整理板端复核清单**

  记录后续上板只需要确认的 3 条事实:
  1. 连续发送普通控制命令时, 串口窗口不再被提示文字刷屏。
  2. 查询命令仍然有正常回包。
  3. 人为制造执行异常时, `ERR` 仍然可见。

## 自检

- [ ] 计划已经覆盖设计文档里的 6 条验收结果: 普通回显删除、`rear` 提示删除、动作完成提示删除、查询保留、错误保留、`print` 静默。
- [ ] 计划里没有代码块、占位词或“后续再补”式空步骤。
- [ ] 文件边界与当前正式主线一致, 没有把旧日志系统恢复、启动日志调整或其他脚本打印混入本轮。
