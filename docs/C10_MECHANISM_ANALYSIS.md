# C10 机制分析 — MTC `PICK_B` 失败（2026-11-09）

数据：C8（3 个 MTC episode）+ C9（6 个）共 9 个 episode 的 step 级 detail。

## 1. 结果
| run | status | planning timeout | planner busy | wall (s) |
| --- | --- | --- | --- | --- |
| C8 mtc-b | FAIL | 1 | 1 | 54.43 |
| C8 mtc-c | PASS | 0 | 0 | 41.91 |
| C8 mtc-f | FAIL | 1 | 1 | 54.39 |
| C9 mtc-h | PASS | 0 | 0 | 33.29 |
| C9 mtc-i | PASS | 0 | 0 | 33.05 |
| C9 mtc-k | PASS | 0 | 0 | 33.31 |
| C9 mtc-m | FAIL | 1 | 1 | 54.34 |
| C9 mtc-p | PASS | 0 | 0 | 32.72 |
| C9 mtc-q | PASS | 0 | 0 | 33.26 |

## 2. 失败 step 的实际 detail
失败 episode 的 `PICK_B` 两次尝试为：
1. `MTC planning failed before execution: planning reply timed out; no motion executed`（error 30）
2. `MTC planning failed before execution: planner busy`（error 30）→ 恢复预算耗尽

即：**第一层失败是 MoveIt 规划服务超时，不是机械臂运动失败**；第二次尝试立即撞上 `planner busy`，
说明超时请求仍占用规划器，1 次恢复预算不足以等待其释放。

## 3. 一致性与局限
- **3/3 失败样本均出现 timeout+busy，6/6 成功样本均无**；
- 失败样本 wall 54.3–54.4 s，成功 32.7–41.9 s（多出的时间即两次规划等待）；
- 不能证明 timeout 是唯一原因（样本小、单机、同一镜像）；
- 该机制只在 MTC 后端存在，FSM 的 `PICK_B` 9/9 均成功。

## 4. 后续（C11 提案，需重新预注册）
最小修复候选（不修改验收器）：
1. MTC 技能后端在规划超时后**等待 planner 空闲**再重试（而非立即重试）；
2. 或把超时映射为可恢复错误并允许一次延迟重试；
3. 回归：C4（默认容差）与 C9（2 cm）重跑，FSM 结果不得变化。
