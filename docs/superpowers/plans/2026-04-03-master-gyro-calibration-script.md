# Master Gyro Calibration Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为主车补一个可直接在板端运行的单文件零漂校准脚本，生成当前主线可直接加载的 `/flash/gyro_offset.txt`。

**Architecture:** 保留 `legacy` 的六轴静止采样与求均值链路，但重写成更清晰的单文件脚本。脚本只负责采样、求均值、写文件和结果提示，不保留无限闪灯之类的附带行为。

**Tech Stack:** MicroPython, `seekfree.IMU660RX`, 板端文件写入, pytest

---

### Task 1: 补脚本行为测试

**Files:**
- Modify: `tests/unit/master/test_attitude_script.py`
- Create: `tests/unit/master/test_calibrate_gyro_script.py`

- [ ] **Step 1: 写失败测试**

覆盖以下行为：
- 脚本支持板端直接运行导入
- 结果文件格式为 6 个逗号分隔浮点数
- 脚本结束后直接返回，不进入无限循环

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/master/test_calibrate_gyro_script.py -q`

- [ ] **Step 3: 最小实现脚本接口**

在 `src/master/script/calibrate_gyro.py` 中实现可调用 `main()` 与直接运行入口。

- [ ] **Step 4: 再跑测试确认通过**

Run: `python3 -m pytest tests/unit/master/test_calibrate_gyro_script.py -q`

### Task 2: 实现单文件零漂校准脚本

**Files:**
- Modify: `src/master/script/calibrate_gyro.py`
- Reference: `src/legacy/script/calibrate_gyro.py`

- [ ] **Step 1: 保留算法链路**

实现以下固定流程：
- 初始化 `IMU660RX`
- 采集固定数量六轴样本
- 求六轴平均值
- 写入 `/flash/gyro_offset.txt`

- [ ] **Step 2: 精简脚本行为**

只保留：
- 开始提示
- 进度提示
- 最终结果提示
- 保存成功/失败提示

删除：
- 无限闪灯
- 永不退出的尾部循环

- [ ] **Step 3: 对齐主线文件格式**

保存格式必须是：
`acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z`

### Task 3: 回归验证

**Files:**
- Modify: `tests/unit/master/test_calibrate_gyro_script.py`
- Verify: `src/master/motion_runtime.py`, `src/master/hw/imu.py`

- [ ] **Step 1: 跑脚本相关测试**

Run: `python3 -m pytest tests/unit/master/test_calibrate_gyro_script.py tests/unit/master/test_attitude_script.py -q`

- [ ] **Step 2: 跑主车相关回归**

Run: `python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py tests/unit/master/test_structure_runtime.py tests/unit/master/test_stability_baseline.py -q`

- [ ] **Step 3: 板端验证**

验证顺序：
- 上传脚本
- 直接运行零漂校准脚本
- 确认 `/flash/gyro_offset.txt` 已生成
- 再跑主循环或姿态诊断脚本，确认零漂误差明显降低
