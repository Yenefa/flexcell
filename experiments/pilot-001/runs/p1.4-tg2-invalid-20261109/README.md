# T-G2（过近放置点）— 无效设计，**不采用**

## 事实
- 探测：`--place-pose 0.05 0 0.0175` → `ROBOT_FAILURE / ERR_SKILL_FAILED / ERR_MOTION_FAILED`；
- 但同一 pose 在后续一次完整运行中被独立验收判 **PASS**（`runtime_fingerprint=aa5ac497…`）；
- 说明该初始条件**不是确定性失败**（物理/时序抖动），无法作为"必须修复"的任务。

## 处置
- **T-G2 设计作废**，不作为 M3-S 第二任务；
- 保留记录（`result.json`/`events.jsonl`）；
- 同时修复了一个真实 bug：`gazebo.latest` 用 `ls | tail` 取目录（按名字排序），可能读到**旧的** result；已改为 `ls -dt | head -1`（按修改时间）。

## 影响
- 该 bug 可能造成 judge 读到旧结果 → 误判 PASS/FAIL；
- 已复核 T-G1 的 3 次成功记录：verdict 中 `place_pose` 均为 0.25，且每次运行均独立重跑，故不受该 bug 影响。
