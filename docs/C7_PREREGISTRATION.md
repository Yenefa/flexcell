# C7 预注册 — 严格验证下的 FSM vs MTC（冻结草案）

> C3–C6 的验证容差为默认 `demo_verify_tolerance_m = 0.06`；C7 检验**收紧验证**是否暴露差异。
> 本文件在运行前提交；指标与判读不得事后修改。

## 1. 场景
- 命令：`--case normal --backend velocity_servo --decision-policy fsm`，`--skill-backend legacy|mtc`；
- 配置覆盖（使用已有 `--config-override` 杠杆，不新增平台代码）：
  `task_fsm_server.ros__parameters.demo_verify_tolerance_m = 0.02`（默认 0.06）；
- 其余世界/技能/预算不变。

## 2. 设计
- 每臂 3 次，交替：FSM, MTC, MTC, FSM, FSM, MTC；
- 单次超时 600 s；失败保留；
- 两臂同容差、同世界、同模型（无 LLM）。

## 3. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | `status=PASS`（收紧容差后仍通过） |
| 次指标 | wall、`zone_a_error_m`/位置误差（若记录） |
| 失败 | error_code、detail |

## 4. 判读规则（冻结）
- 若两臂都仍 3/3：记录"收紧到 2 cm 未区分两臂"，不宣称等价；
- 若出现差异：报告方向与 n=3 的不确定性，不宣称显著；
- 不得修改容差/验收器让某臂通过；
- 与 C3（默认容差）比较时说明容差不同，不可直接混算。

## 5. 边界
- 仿真（M3-S）；单场景；
- 结果写入 `setup/acceptance/c7_strict_tolerance_20261109/`。

## 6. 结果附录（运行后追加，不改规则）
- 6/6 PASS：FSM 平均 14.101 s，MTC 平均 16.440 s（+2.338 s ≈ +16.6%）；
- fingerprint 确认容差覆盖生效；
- 记录：`setup/acceptance/c7_strict_tolerance_20261109/`；
- 结论：**2 cm 容差未区分两臂**，MTC 仍更慢（n=3，探索性）。
