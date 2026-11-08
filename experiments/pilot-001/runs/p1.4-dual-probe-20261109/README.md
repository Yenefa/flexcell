# Track A 组合任务探测（2026-11-09）— **设计受阻**

## 尝试
`--case dual_object --place-pose 0.45 0 0.0175`（两个对象，第一位姿故意不可达）。

## 结果（真实 Gazebo）
| 项 | 值 |
| --- | --- |
| status | **PASS** |
| trace | `PICK_A→PLACE_A→VERIFY_A→PICK_B→PLACE_B→VERIFY_B` 全部 OK |

**意外**：`--place-pose` 在 `dual_object` 场景未产生失败（在 `normal`/`regrasp` 中 0.45 会稳定失败）。

## 结论与阻塞
- `dual_object` 不能靠 place-pose 制造确定性初始失败；
- 要建立真实组合任务，需要新的**计划级杠杆**（例如按对象指定位姿/分配），
  这属于平台改动，需单独设计与验收，不在本轮临时修改；
- 标记 **BLOCKED（组合任务脚手架）**；已有合成层组合任务（P1.2 T-B）仍有效。

## 证据
- `result.json`、`episode.json`（本次真实运行，保留）
