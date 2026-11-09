# W6 迁移试点（n=1/臂，2026-11-09）

| arm | success | iters | tokens | final place_pose | verdict |
| --- | --- | --- | --- | --- | --- |
| warm | true | 4 | 3840 | [0.25,0,0.0175] | PASS |
| cold | false | 5 | 6260 | [0.45,0,0.0175] | REGRASP_BLOCKED_FIRST_TASK |

## 观察（n=1，仅方向性）
- **Warm**（带迁移归因）4 轮解决：`place_pose` 0.45 → 0.25，独立验收 PASS；
- **Cold**（裸任务，须自行诊断）5 轮后**未修改 plan**，验收仍 `REGRASP_BLOCKED_FIRST_TASK`；
- 方向与预注册假设一致（迁移知识可能降低适应成本），但 **n=1**，不得下结论；
- Cold 的失败也可能是"未动手"而非"诊断不了"，正式 3+3 需观察调用序列。

## 下一步
按 `docs/W6_TRANSFER_PREREGISTRATION.md` 跑 3+3（C,W,W,C,C,W）。
