# C11 预注册 — MTC 规划超时的有界重试（最小修复）

> C10 归因：3/3 失败 episode 均出现 `planning reply timed out` + 紧随的 `planner busy`；
> 6/6 成功无。C11 在 **skill 客户端**加入有界重试（等待后重试），不改规划器 C++、不改任何门。

## 1. 修改（允许范围）
- 文件：`src/flexcell/flexcell_skills/flexcell_skills/mtc_motion.py`；
- 行为：`prepare()` 在以下两种结果时最多重试 2 次（间隔 3 s）：
  1. `wait_future` 超时（移除 pending 后重试）；
  2. planner 返回 `planner busy`；
- 总等待上限 ~9 s；其余错误不重试；记录 `planning_audit`。

## 2. 评估设计
- **目标**：2 cm 容差 dual_object，MTC **6 次**（C8/C9 基线 6/9）；
- **回归 A**：同场景 FSM 3 次（应保持 3/3）；
- **回归 B**：默认容差 dual_object MTC 3 次（C4 基线 3/3，应保持 3/3）；
- 共 12 次真实 Gazebo；单次超时 600 s。

## 3. 判读规则（冻结）
- 目标 ≥5/6 且回归 A/B 全 PASS → 记"**有界重试改善了 MTC 规划超时**（探索性）"；
- 目标 <5/6 → 记"未改善"；
- 任一回归失败 → 记 **regression loss**，拒绝该修复；
- 不修改验收器/阈值/世界；n 小，不宣称显著。

## 4. 记录
- `setup/acceptance/c11_mtc_retry_20261109/`；
- 代码改动 + 单元测试（mock 重试路径）。
