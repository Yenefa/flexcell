# C8 预注册 — 严格容差下的 dual_object（FSM vs MTC，3+3）

> C7 在 normal 场景把容差收紧到 2 cm 未区分两臂；C8 把同一严格度应用到 **dual_object**，
> 检验多对象场景下是否出现差异。

## 1. 场景
- 命令：`--case dual_object --backend velocity_servo --decision-policy fsm`，`--skill-backend legacy|mtc`；
- 配置覆盖：`task_fsm_server.demo_verify_tolerance_m = 0.02`（默认 0.06），经既有 `--config-override`；
- 其余世界/技能/预算不变。

## 2. 设计
- 每臂 3 次，交替：FSM, MTC, MTC, FSM, FSM, MTC；
- 单次超时 600 s；失败保留；
- 同容差、同世界、同模型（无 LLM）。

## 3. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | `status=PASS` |
| 次指标 | wall、`zone_a_error_m`/`zone_b_error_m`（若记录） |
| 失败 | error_code、detail |

## 4. 判读规则（冻结）
- 两臂都 3/3 → 记"2 cm 容差下 dual_object 未区分两臂"，不宣称等价；
- 出现差异 → 报告方向与 n=3 不确定性，不宣称显著；
- 不得修改容差/验收器；
- 与 C4（默认容差）比较时说明容差不同，不可混算。

## 5. 边界
- 仿真（M3-S）；单场景；
- 结果写入 `setup/acceptance/c8_strict_dual_20261109/`。
