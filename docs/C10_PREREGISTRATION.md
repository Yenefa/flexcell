# C10 预注册 — MTC `PICK_B` 失败机制归因（只分析，不新增验收）

> C8/C9 显示 MTC 在 dual_object + 2 cm 下 3/9 失败，失败均为 `PICK_B`。
> C10 只用既有 episode 做机制归因，**不新增模拟、不修改门/阈值**。

## 1. 数据来源
- C8 的 3 个 MTC episode（1 失败/2 成功）；
- C9 的 6 个 MTC episode（2 失败/4 成功）；
- 共 9 个 episode，比较失败与成功样本的 step 级 `executor_result.detail`。

## 2. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| planning timeout | detail 含 "planning reply timed out" 的 step 数 |
| planner busy | detail 含 "planner busy" 的 step 数 |
| wall | `final_state.duration_s` |

## 3. 判读规则
- 若失败样本全部出现 timeout，且成功样本无一出现 → 记"**机制与失败相关**"，不宣称因果；
- 若不一致 → 如实记录，不强行解释；
- 不改任何验收器/阈值；结果仅用于提出后续最小修复候选（C11 需重新预注册）。

## 4. 记录
- `setup/acceptance/c10_mechanism_20261109/`（派生数据 + verify.py）。
