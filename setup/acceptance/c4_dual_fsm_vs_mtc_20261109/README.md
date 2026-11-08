# C4 — dual_object 场景 FSM vs MTC，同条件 3+3（2026-11-09）

协议：[`docs/C4_PREREGISTRATION.md`](../../../docs/C4_PREREGISTRATION.md)（运行前冻结）。
运行顺序：FSM, MTC, MTC, FSM, FSM, MTC。

| run | arm | status | wall (s) | 阶段数 |
| --- | --- | --- | --- | --- |
| legacy-a | FSM | PASS | 28.564 | 6 |
| mtc-b | MTC | PASS | 33.327 | 6 |
| mtc-c | MTC | PASS | 33.635 | 6 |
| legacy-d | FSM | PASS | 28.518 | 6 |
| legacy-e | FSM | PASS | 28.566 | 6 |
| mtc-f | MTC | PASS | 36.143 | 6 |

## 汇总
| 指标 | FSM | MTC |
| --- | --- | --- |
| 两对象成功 | **3/3** | **3/3** |
| 平均 wall | **28.549 s** | **34.368 s** |
| 差值 | — | **+5.819 s（≈ +20.4%）** |
| trace | `PICK_A→PLACE_A→VERIFY_A→PICK_B→PLACE_B→VERIFY_B` | 同 |

## 判读（按协议）
- 主指标 **无成功差异**；
- MTC 在本样本中平均慢 **5.819 s（≈20%）**，n=3，**不宣称显著**；
- 与 C3（单对象，MTC +3.6 s ≈ +23%）方向一致：**MTC 时间成本更高**，成功率相同；
- 不写"MTC 更差/更好"；
- 附注：预热阶段有一次 legacy-a 因**脚本参数错误**（ROS_DOMAIN_ID）失败，已重跑；错误运行日志保留在 `/tmp`，不入证据。

```bash
python3 setup/acceptance/c4_dual_fsm_vs_mtc_20261109/verify.py
```
