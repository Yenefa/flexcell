# C3 — FSM（控制）vs MTC（treatment），同条件 n=3/臂

协议：[`docs/C3_FSM_VS_MTC_PROTOCOL.md`](../../../docs/C3_FSM_VS_MTC_PROTOCOL.md)（运行前冻结，未修改）。
运行顺序按协议交替：FSM → MTC → MTC → FSM → FSM → MTC。

| run | arm | status | outcome | wall (s) | evidence |
| --- | --- | --- | --- | --- | --- |
| legacy-a | FSM | PASS | SUCCEEDED | 14.671 | `pick_place_v1-1d3c5e38` |
| mtc-b | MTC | PASS | SUCCEEDED | 16.771 | `pick_place_v1-de559810` |
| mtc-c | MTC | PASS | SUCCEEDED | 16.600 | `pick_place_v1-22946a62` |
| legacy-d | FSM | PASS | SUCCEEDED | 17.853 | `pick_place_v1-6547260f` |
| legacy-e | FSM | PASS | SUCCEEDED | 14.588 | `pick_place_v1-3ff4649b` |
| mtc-f | MTC | PASS | SUCCEEDED | 24.520 | `pick_place_v1-1132f360` |

## 汇总
| 指标 | FSM | MTC |
| --- | --- | --- |
| 任务成功 | **3/3** | **3/3** |
| 平均执行时间 | 15.70 s | 19.30 s |
| 恢复次数（trace 中 RECOVERY） | 0 | 0 |
| 模型 token 成本 | 0 | 0 |
| runtime fingerprint | `aa5ac497…` | `33b420d1…` |

## 判读（按协议预注册规则）
- 主指标：两臂 **3/3**，**无差异**；
- 次要指标：MTC 在本样本中平均慢约 **3.6 s（≈23%）**，n=3，**不作显著性结论**；
- 无 false success、无失败记录需要保留（两臂都通过）；
- 结论口径：**"无成功差异，MTC 时间成本略高（探索性）"**，不得写成"MTC 更差"或"更好"。

```bash
python3 setup/acceptance/c3_fsm_vs_mtc_20261109/verify.py
```
