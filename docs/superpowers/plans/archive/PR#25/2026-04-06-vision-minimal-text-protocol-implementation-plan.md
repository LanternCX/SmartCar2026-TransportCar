# 视觉最小文本协议实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项执行。步骤使用复选框语法跟踪。

**Goal:** 让 `SmartCar2026-TransportCar` 与 `../Smartcar2026-Vision` 在同一轮内切到统一的视觉最小文本协议, 并用 TDD 验证主车接收与视觉发送都按新口径工作。

**Architecture:** 先在两个仓库分别补失败测试, 锁死新协议格式、`x/y` 语义和旧字段退出条件, 再做最小实现修改。主车侧只收口视觉解析与输入整理, 视觉侧只收口正式发送格式与对应文档测试, 最后用组合验证确认两边同步切换。

**Tech Stack:** Python 3.8+、pytest、MicroPython/OpenArt 主程序、主车视觉输入解析链

---

## 文件边界

### 主车仓库 `SmartCar2026-TransportCar`

- 修改: `src/master/vision/parser.py`
  负责解析新的最小文本协议, 删除对旧正式字段的依赖。
- 修改: `src/master/vision/ingress.py`
  负责把最小协议整理成主车内部统一观测, 清掉对 `target/camera_id/bbox` 的正式输入依赖。
- 修改: `tests/unit/master/test_vision_ingress.py`
  锁定主车接收最小协议后的输入整理、双 UART 行为和旧字段退出行为。
- 新增或修改: `tests/unit/master/test_vision_parser.py`
  锁定新协议解析规则与异常输入处理。
- 修改: `.agents/skills/using-rules/references/openart-protocol.md`
  作为主车仓库中的正式视觉协议正文, 同步到最小文本协议口径。
- 修改: `tests/hil/2026-03-master-minimal-runtime.md` 或新增同主题 HIL 记录
  作为本轮现场抓包、双 UART 观察与 `UART3` 输出跳变对比的留证入口。

### 视觉仓库 `../Smartcar2026-Vision`

- 修改: `main.py`
  负责发送最小文本协议, 保持 `x/y` 语义不变, 移除正式输出中的旧字段。
- 修改: `tests/unit/test_vision_protocol_rebuild.py`
  锁定新的格式化输出、无效帧格式和运行时发送行为。
- 修改: `tests/contract/test_main_vision_protocol_contract.py`
  锁定视觉主程序不再包含旧正式字段, 并声明新协议格式片段。
- 修改: `docs/Protocol.md`
  更新视觉仓库正式协议正文到新口径。
- 修改: `README.md`
  更新对外入口说明, 与正式协议正文一致。

### 组合验证

- 记录: 两仓库联调验证结果
  用于确认两边都切到新协议后的组合版本行为正常。

## Task 1: 主车视觉接收链切到最小协议

**Files:**
- Create or Modify: `tests/unit/master/test_vision_parser.py`
- Modify: `tests/unit/master/test_vision_ingress.py`
- Modify: `src/master/vision/parser.py`
- Modify: `src/master/vision/ingress.py`

- [ ] **Step 1: 先写主车视觉接收链失败测试**
  为最小协议新增失败测试, 至少覆盖以下行为:
  - `v=1,s=12,x=7,y=50` 能解析成有效观测。
  - `v=0,s=13` 能解析成无效观测。
  - 缺少 `s`、缺少 `x/y`、重复字段时, parser 直接抛解析异常, ingress 最终按无效输入处理。
  - 双 UART 都能接收最小协议, 且仅凭来源串口完成仲裁。
  - 旧正式字段退出后, 当前主线仍能选择最新有效目标。

- [ ] **Step 2: 运行主车视觉接收链相关测试并确认先失败**
  运行只覆盖 parser / ingress 的最小测试集合, 确认失败原因来自新协议尚未实现或旧字段依赖尚未清理, 不是测试拼写或环境问题。

- [ ] **Step 3: 最小修改 `parser.py` 与 `ingress.py`**
  只实现通过失败测试所需的最小接收链修改, 不顺手做额外重构, 也不引入旧字段兼容层。

- [ ] **Step 4: 运行主车视觉单测并确认通过**
  至少覆盖 parser + ingress + 相关 app/decision 受影响测试, 确认主车主线仍能产出稳定控制输入。

## Task 2: 视觉仓库发送格式切到最小协议

**Files:**
- Modify: `../Smartcar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- Modify: `../Smartcar2026-Vision/main.py`

- [ ] **Step 1: 先写视觉侧失败测试**
  锁定以下行为:
  - 有效帧格式变为 `v=1,s=<seq>,x=<x>,y=<y>`。
  - 无效帧格式变为 `v=0,s=<seq>`。
  - 发送行为仍保留 `CRLF`。
  - `x/y` 的像素语义与当前逻辑一致。

- [ ] **Step 2: 运行视觉仓库对应单测并确认先失败**
  确认失败来自旧格式仍在输出。

- [ ] **Step 3: 最小修改 `main.py`**
  只改正式发送格式和相关最小辅助逻辑, 不顺手改目标选择和图像处理行为。

- [ ] **Step 4: 再次运行视觉仓库单测并确认转绿**
  确认新的最小协议格式成为唯一正式输出。

## Task 3: 两边协议文档与契约测试同步更新

**Files:**
- Modify: `../Smartcar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- Modify: `../Smartcar2026-Vision/docs/Protocol.md`
- Modify: `../Smartcar2026-Vision/README.md`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-TransportCar/.agents/skills/using-rules/references/openart-protocol.md`

- [ ] **Step 1: 先写或改失败契约测试**
  让测试或文档检查明确拒绝旧长报文正式字段, 并要求新最小协议片段出现在视觉仓库主程序、视觉仓库文档和主车仓库正式协议正文中。

- [ ] **Step 2: 运行契约测试并确认先失败**
  确认失败来自旧文档和旧契约尚未更新。

- [ ] **Step 3: 最小更新两边正式文档**
  把主车仓库 `openart-protocol.md` 与视觉仓库 `docs/Protocol.md`、`README.md` 都切到新口径, 且文本语义一致。

- [ ] **Step 4: 运行契约测试并确认通过**
  确认两边不再同时保留旧长报文作为正式说明。

## Task 4: 组合回归与跨仓库联调验证

**Files:**
- Verify: `SmartCar2026-TransportCar/tests/unit/...`
- Verify: `../Smartcar2026-Vision/tests/unit/...`
- Verify: `../Smartcar2026-Vision/tests/contract/...`
- Record: `tests/hil/2026-03-master-minimal-runtime.md` 或新增同主题 HIL 记录

- [ ] **Step 1: 运行主车仓库受影响测试集合**
  覆盖主车视觉解析、输入整理以及受影响的上层行为测试。

- [ ] **Step 2: 运行视觉仓库受影响测试集合**
  覆盖视觉主程序单测与契约测试。

- [ ] **Step 3: 按规格记录主车现场验证项**
  在 HIL 记录里逐项留证以下内容:
  - `UART6` 连续不少于 200 帧抓包逐行完整。
  - `UART8` 连续不少于 200 帧抓包逐行完整。
  - 主车连续观察 200 拍时, 因解析失败导致的无效拍次数为 0。
  - 同一观察窗口内, 不出现连续 3 拍及以上由格式错误导致的无效帧。
  - `UART3` 输出跳变次数与当前版本留档样本做前后对比。

- [ ] **Step 4: 用组合版本检查协议一致性**
  确认两边都已切到新协议后的组合版本中, 示例报文、测试夹具、正式文档和人工抓包记录一致。

- [ ] **Step 5: 记录验证结论**
  记录是否达成“报文缩短、两边语义一致、旧正式字段退出”的目标, 并注明若仍有链路问题应继续排查的位置。

## 执行方式

本次按用户要求, 直接选择 **Subagent-Driven** 执行。

执行要求:

1. 每个任务由独立 subagent 执行。
2. 每个任务都必须遵守 TDD: 先写失败测试, 先看见失败, 再做最小实现。
3. 一个任务完成后先回到主会话复查, 再放行下一个任务。
4. 不在任务中顺手扩大范围。
