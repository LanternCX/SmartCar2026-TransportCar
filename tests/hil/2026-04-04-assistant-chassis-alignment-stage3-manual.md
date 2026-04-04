# 2026-04-04 辅车底盘对齐 Stage 3 人工联调留证

## 状态

- 当前状态: 待用户回板执行 Stage 3 人工联调
- 留证路径: `tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md`
- 附件预留路径: `tests/hil/artifacts/2026-04-04-assistant-chassis-alignment-stage3-manual/`
- 主车对齐参考提交: `c164e8d`、`c95f10c`
- 本页边界: 只记录 Stage 3 人工联调与最终人工结论, 不创建 Stage 2 文档, 不再使用 Stage 2 流程
- 主车相关说明: 主车工作区改动属于用户自己的调试, 本页不处理, 也不把它视为本轮阻塞

## 失败分类

- `boot_failed`: 无法正常启动到辅车主循环
- `log_missing`: 关键启动日志缺失或无法定位
- `wheel_direction_mismatch`: 左右轮方向与主车对齐事实不一致
- `gyro_offset_missing`: 零漂文件不存在
- `gyro_offset_not_loaded`: 零漂文件存在但运行时未实际加载
- `gyro_offset_invalid`: 零漂值明显异常或加载后表现不合理
- `ident_missing`: 辨识参数文件不存在
- `ident_not_loaded`: 辨识参数文件存在但运行时未实际加载
- `ident_invalid`: 辨识参数明显异常或加载后表现不合理
- `tick_chain_incomplete`: 动态节拍证据不能覆盖到底盘控制链关键环节
- `diag_surface_regressed`: `health` / `tick` 等最小诊断面不可用或明显退化
- `observe_failed`: 已启动但人工观察无法形成可信结论
- `hil_pending`: 还未连板执行

## 启动日志关键字与定位

- `ident_lookup_loaded` 代码记录位置: `src/assistant/motion_runtime.py:125` 与 `src/assistant/motion_runtime.py:650`
- `gyro_offsets_loaded` 代码记录位置: `src/assistant/motion_runtime.py:138` 与 `src/assistant/motion_runtime.py:651`
- `capture_ticker_ready` 代码记录位置: `src/assistant/main.py:98-113`
- 启动日志原始文本模板 1:
  `[assistant.motion] ident_lookup_loaded | path=/flash/ident_params.txt, wheel_ident={...}`
- 启动日志原始文本模板 2:
  `[assistant.motion] gyro_offsets_loaded | gyro_offsets=(...), path=/flash/gyro_offset.txt`
- 启动日志原始文本模板 3:
  `[assistant.main] capture_ticker_ready | count=4`
- 实测启动日志路径:
  `待补充, 建议保存到 tests/hil/artifacts/2026-04-04-assistant-chassis-alignment-stage3-manual/startup.log`

## 运行前填写

- 执行人: 待补充
- 执行时间: 待补充
- 板端版本标识: 待补充
- 参数版本标识: 待补充
- 录像或照片路径: `tests/hil/artifacts/2026-04-04-assistant-chassis-alignment-stage3-manual/`

## 主机侧先验证据

- 已要求的主机侧回归: `python3 -m pytest tests/unit/assistant -q`
- 已要求的改动面自检: `git diff -- tests/unit/assistant src/assistant tests/hil/2026-04-04-assistant-chassis-alignment-stage3-manual.md docs/superpowers/specs/2026-04-04-assistant-chassis-debug-alignment-design.md`
- 关键代码证据:
  - `src/assistant/main.py:98-113` 已建立采样触发链并打印 `capture_ticker_ready`
  - `src/assistant/ctrl/attitude.py:138-145` 以实时节拍推进姿态更新
  - `src/assistant/motion_runtime.py:300-314` 将同一拍节拍继续传到编码器滤波与轮速更新链
  - `src/assistant/motion_runtime.py:641-656` 启动时加载辨识参数与零漂并尝试实际应用到 IMU
- Stage 3 人工联调只负责把这些代码侧证据和板端现象对上, 不在本页杜撰实测结果

## Stage 3 步骤

### 步骤 1: 启动与关键日志定位

- 步骤:
  1. 正常启动辅车运行分支。
  2. 保存完整启动日志。
  3. 在启动日志中定位 `capture_ticker_ready`、`ident_lookup_loaded`、`gyro_offsets_loaded` 三条记录。
- 预期:
  1. 能进入辅车主循环, 不是停在校准或辨识分支。
  2. 三条关键日志都能找到。
  3. `ident_lookup_loaded` 指向 `/flash/ident_params.txt`。
  4. `gyro_offsets_loaded` 指向 `/flash/gyro_offset.txt`。
- 实测: 待补充
- 结论: 待补充
- 失败分类: `hil_pending`

### 步骤 2: 左右轮方向检查

- 步骤:
  1. 在安全支撑条件下给一个短时、低风险的前进动作。
  2. 观察左右轮实际转向是否与主车当前对齐事实一致。
  3. 再给一个短时原地转动动作, 复核左右轮方向组合是否一致。
- 预期:
  1. 前进行为不出现某一侧明显反向。
  2. 原地转动时左右轮方向组合符合主车对齐基线。
  3. 不再出现“只能靠翻符号试错”的现象。
- 实测: 待补充
- 结论: 待补充
- 失败分类: `wheel_direction_mismatch`

### 步骤 3: 零漂文件存在性与实际加载检查

- 步骤:
  1. 确认板端存在 `/flash/gyro_offset.txt`。
  2. 记录文件内容摘要。
  3. 对照启动日志中的 `gyro_offsets_loaded` 原始文本, 确认运行时确实加载了同一路径。
  4. 静止放置 5 到 10 秒, 观察航向是否仍明显持续漂移。
- 预期:
  1. 文件存在。
  2. 启动日志里能看到 `gyro_offsets_loaded`。
  3. 日志里的数值与文件内容一致或可解释一致。
  4. 静止时航向表现基本合理, 不出现明显持续自转趋势。
- 实测: 待补充
- 结论: 待补充
- 失败分类: `gyro_offset_missing` / `gyro_offset_not_loaded` / `gyro_offset_invalid`

### 步骤 4: 辨识参数文件存在性与实际加载检查

- 步骤:
  1. 确认板端存在 `/flash/ident_params.txt`。
  2. 记录三轮参数摘要。
  3. 对照启动日志中的 `ident_lookup_loaded` 原始文本, 确认运行时确实加载了同一路径。
  4. 给低速动作, 观察三轮响应是否不存在明显单轮失控或完全不跟随。
- 预期:
  1. 文件存在。
  2. 启动日志里能看到 `ident_lookup_loaded`。
  3. 日志里的三轮参数摘要与文件一致或可解释一致。
  4. 低速动作表现基本合理, 不出现明显单轮参数缺失带来的离谱响应。
- 实测: 待补充
- 结论: 待补充
- 失败分类: `ident_missing` / `ident_not_loaded` / `ident_invalid`

### 步骤 5: 动态节拍证据覆盖检查

- 步骤:
  1. 先用启动日志确认 `capture_ticker_ready` 已出现。
  2. 结合主机侧已通过的回归, 核对实时节拍已经贯穿姿态更新、编码器滤波和轮速控制关键环节。
  3. 在板端做短时动作与短暂停顿切换, 观察动作收放是否没有明显固定节拍拖尾。
- 预期:
  1. 不是只修到姿态前半段, 而是关键控制环节都吃到同一拍节拍证据。
  2. 板端观察不出现明显“前半段更新了、后半段仍像固定拍”的割裂感。
  3. 代码证据与板端现象能互相对上。
- 实测: 待补充
- 结论: 待补充
- 失败分类: `tick_chain_incomplete`

### 步骤 6: 最小诊断面可用性检查

- 步骤:
  1. 复核当前最小查询面仍能拿到状态回包。
  2. 复核主循环 `tick` 推进路径仍可持续运行, 不会在启动后很快失活。
  3. 如果当前联调环境暴露了 `health` 诊断入口, 一并记录其结果。
- 预期:
  1. 最小诊断面仍可用, 没因本轮对齐失活。
  2. 至少能确认状态查询和周期推进没有明显回归。
  3. 若存在 `health` 入口, 返回结果应可读且不报错。
- 实测: 待补充
- 结论: 待补充
- 失败分类: `diag_surface_regressed`

### 步骤 7: 启动日志原始文本留证

- 步骤:
  1. 直接粘贴 `ident_lookup_loaded` 原始日志。
  2. 直接粘贴 `gyro_offsets_loaded` 原始日志。
  3. 如有需要, 同步粘贴 `capture_ticker_ready` 原始日志。
- 预期:
  1. 原始文本能直接支撑文件已加载的结论。
  2. 记录内容不是转述, 而是可回看原文。
- `ident_lookup_loaded` 原始文本: 待补充
- `gyro_offsets_loaded` 原始文本: 待补充
- `capture_ticker_ready` 原始文本: 待补充
- 结论: 待补充
- 失败分类: `log_missing`

## 最终结论

- Stage 3 是否完成: 待补充
- 当前版本是否可视为已按主车底盘基线完成辅车对齐: 待补充
- 是否还需要继续改代码: 待补充
- 备注: 在未填写本页实测结果前, 当前只能视为“主机侧已准备好, 等用户回来做 Stage 3 人工联调”
