# B2c — FSM vs Calibrated Hybrid，同条件 3+3（2026-11-09）

协议：[`docs/B2C_PROTOCOL.md`](../../../docs/B2C_PROTOCOL.md)（运行前冻结，未修改）。
运行顺序：F → H → H → F → F → H。

| run | arm | status | wall (s) | 路由 | fast 延迟 (ms) |
| --- | --- | --- | --- | --- | --- |
| fsm-a | FSM | PASS | 14.542 | — | — |
| hybrid-b | Hybrid | PASS | 18.097 | 3/3 jev | 1019 / 1240 / 1506 |
| hybrid-c | Hybrid | PASS | 17.726 | 3/3 jev | 1262 / 1210 / 1169 |
| fsm-d | FSM | PASS | 14.133 | — | — |
| fsm-e | FSM | PASS | 13.980 | — | — |
| hybrid-f | Hybrid | PASS | 17.134 | 3/3 jev | 813 / 1170 / 1177 |

## 汇总
| 指标 | FSM | Hybrid |
| --- | --- | --- |
| 任务成功 | **3/3** | **3/3** |
| 平均 wall | **14.218 s** | **17.652 s** |
| 差值 | — | **+3.434 s（≈ +24%）** |
| fast 命中 | — | **9/9 路由决策**（bootstrap 除外） |
| escalation | — | **0** |
| fast 延迟 | — | 813–1506 ms |
| 远端 token | 0 | ≈ 1.2–1.5k/decision |
| fingerprint | `7808f64e…` | `fdc81ed9…` |

## 判读（按协议）
- 主指标 **无成功差异**（3/3 vs 3/3）；
- Hybrid 在本样本中平均慢 **3.434 s（≈24%）**，n=3，**不宣称显著**；
- fast 命中率 **100%**、零 escalation：校准路由按预期工作；
- 成本：每次运行 3 次远端调用（~3.9k tokens），延迟 0.8–1.5 s/decision；
- 结论口径：**"成功率无差异，远端 fast 臂带来约 +24% 的 wall 时间成本"**；
- 不得写成"hybrid 更好/更差"。

```bash
python3 setup/acceptance/b2c_fsm_vs_hybrid_20261109/verify.py
```
