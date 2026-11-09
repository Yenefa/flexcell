# C8 — 严格 2 cm 容差下的 dual_object FSM vs MTC（3+3）

协议：[`docs/C8_PREREGISTRATION.md`](../../../docs/C8_PREREGISTRATION.md)。
配置覆盖：`task_fsm_server.demo_verify_tolerance_m = 0.02`（默认 0.06）。

| run | arm | status | wall (s) | error |
| --- | --- | --- | --- | --- |
| legacy-a | fsm | PASS | 28.149 | ERR_NONE |
| mtc-b | mtc | ROBOT_FAILURE | 54.436 | ERR_RECOVERY_EXHAUSTED |
| mtc-c | mtc | PASS | 41.911 | ERR_NONE |
| legacy-d | fsm | PASS | 28.89 | ERR_NONE |
| legacy-e | fsm | PASS | 27.931 | ERR_NONE |
| mtc-f | mtc | ROBOT_FAILURE | 54.399 | ERR_RECOVERY_EXHAUSTED |

| 指标 | FSM | MTC |
| --- | --- | --- |
| 成功 | **3/3** | **1/3** |
| 平均 wall（全部） | 28.323 s | 50.249 s |
| 平均 wall（仅成功） | 28.323 s | 41.911 s |

## 失败详情（两次都是 MTC）
- `PICK_A→PLACE_A→VERIFY_A→PICK_B(attempt=1):FAIL:ERR_MOTION_FAILED`
  → `RECOVERY` → `pick attempt 2 failed (error 30)` → `BUDGET_EXHAUSTED`；
- 失败点在**第二个对象的抓取**（PICK_B），不是验证容差本身；
- FSM 同场景 3/3 通过，`zone_a/b` 误差 ~5–12 mm（均在 2 cm 内）。

## 判读（按协议）
- 这是 C3–C8 中**首次出现成功差异**（FSM 3/3 vs MTC 1/3）；
- **n=3，Fisher 精确检验 p=0.1，不宣称显著**；也不宣称"MTC 更差"；
- 失败机制是 PICK_B 运动失败 + 恢复预算耗尽，与 2 cm 容差无直接因果证据；
- 与 C4（默认容差 3/3 vs 3/3）比较时说明容差不同，不可混算。

```bash
python3 setup/acceptance/c8_strict_dual_20261109/verify.py
```
