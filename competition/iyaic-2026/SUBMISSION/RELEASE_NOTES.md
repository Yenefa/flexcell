# RELEASE NOTES — 创意组参赛材料 v1.0

- 版本：v1.0（2026-11-08 打包工具与内容基线）
- 项目：AgenticFlex — 面向教育与柔性装配的智能体驱动机器人工作单元
- 组别：IYAIC 2026 河南赛区 · 人工智能与机器人创新赛（创意组）

## 包内清单（`make_release.py` 生成）
- 项目创意计划书.md（7 段 + 关键指标 + 团队分工 + 原创性/完成度声明）
- 创意组_AgenticFlex_展示PPT.pptx（14 页）
- 答辩逐字稿.md、演示脚本.md、现场操作卡.md、PPT大纲.md、提交清单.md
- evidence/：EVIDENCE.md、demo_sim.mp4（29.6s）、frames/*.png（真实相机帧）

## 自检结果
- 占位符：填队伍信息后 **0 剩余**
- `check_consistency.py`：**PASS**（台账与逐字稿数字一致）
- `score_check.py`：**PASS**（6 项评分权重全覆盖，合计 100）
- `package.py`：官方命名 zip（16 文件）；示例 ~350 KB
- 当前 main 核心窗口：`FUNCTIONAL_WINDOW_PASS`，`window_id=8b1c18af…`，运行时指纹 **`dd456b9b…`**

## CI
- `ci`（离线测试）push 成功：`2fb1fbf`（run 42474689388）。
- `trusted-simulation` 在含运行代码的提交上成功：`751e466` / `7fecbe2`（run 42472385068 / 42468818560）；其后仅文档提交会因并发组取消 sim（预期，非失败）。

## 运行环境（演示可复跑）
- WSL2 Ubuntu 24.04，ROS 2 Jazzy + Gazebo Harmonic，Mesa llvmpipe（无 GPU）。
- 现场操作卡含一键命令与故障兜底。

## 声明
- 一次有界功能窗口验证，**非成功率、非 n≥50**；不夸大。
