# C5 — recovery_once 场景 FSM vs MTC，同条件 3+3（2026-11-09）

协议：[`docs/C5_PREREGISTRATION.md`](../../../docs/C5_PREREGISTRATION.md)（运行前冻结）。
运行顺序：FSM, MTC, MTC, FSM, FSM, MTC。

| run | arm | status | wall (s) | RECOVERY 次数 |
| --- | --- | --- | --- | --- |
| legacy-a | fsm | PASS | 14.218 | 1 |
| mtc-b | mtc | PASS | 16.341 | 1 |
| mtc-c | mtc | PASS | 16.326 | 1 |
| legacy-d | fsm | PASS | 14.214 | 1 |
| legacy-e | fsm | PASS | 14.369 | 1 |
| mtc-f | mtc | PASS | 16.323 | 1 |

| 指标 | FSM | MTC |
| --- | --- | --- |
| 恢复后成功 | **3/3** | **3/3** |
| 平均 wall | **14.267 s** | **16.330 s（+2.063 s ≈ +14.5%）** |
| 每 run recovery | 1 | 1 |

## 判读（按协议）
- 主指标 **无成功差异**：两臂都在一次 `PICK_A:FAIL` 后由 `RECOVERY:REOBSERVE+RETRY` 恢复并完成；
- MTC 平均慢 **2.063 s**，n=3，**不宣称显著**；
- 与 C3/C4 方向一致（MTC 时间成本更高、成功率相同）；
- 不写"MTC 更好/更差"。

```bash
python3 setup/acceptance/c5_recovery_fsm_vs_mtc_20261109/verify.py
```
