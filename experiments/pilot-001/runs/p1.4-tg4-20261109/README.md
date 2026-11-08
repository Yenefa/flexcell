# P1.4 — T-G4：两对象组合任务（真实 Gazebo），LLM 修复成功

## 任务
- `case=dual_object`；**第一个对象正常完成**，第二个对象的 `zone_2` 初始为不可达 `[0.45,0.05,0.0175]`；
- 探测确认失败：`PICK_A→PLACE_A→VERIFY_A→PICK_B→PLACE_B:FAIL`（`ERR_MOTION_FAILED`）；
- 平台新增 `--zone-2-pose` 杠杆（sim_smoke + sim_profile），验收脚本按 plan 复跑同一 case/zone。

## 结果（`result.json`）
| 项 | 值 |
| --- | --- |
| success | **true**（3 轮，3432 tokens） |
| 修改 | agent 写 `zone_2_pose=[0.20,0.05,0.0175]` |
| 独立验收 | `gate/acceptance.py` 重跑真实 Gazebo（dual_object）→ **PASS** |
| fingerprint | `b81c5d49…` |
| 证据完整度 | 1.0；false_success 0 |

## 意义
- **Track A 的组合类真实任务成立**：不是只改第一对象位姿，而是两个对象的任务里修第二个对象的落点；
- 此前 `--place-pose` 在 dual_object 上不产生失败（已记录），本轮用 `zone_2` 参数杠杆解决；
- 仍为 n=1；组合任务的可靠性待重复。
