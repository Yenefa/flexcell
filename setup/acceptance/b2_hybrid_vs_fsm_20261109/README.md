# B2 试点 — FSM vs Hybrid（fast 臂不可用，2026-11-09）

协议：[`docs/B2_HYBRID_VS_FSM_PROTOCOL.md`](../../../docs/B2_HYBRID_VS_FSM_PROTOCOL.md)（阈值冻结 0.85）。

| arm | status | outcome | wall (s) | 决策 trace |
| --- | --- | --- | --- | --- |
| FSM（控制） | PASS | SUCCEEDED | 14.501 | 无 trace（纯 FSM） |
| Hybrid（处理） | PASS | SUCCEEDED | 14.608 | 4 步：bootstrap→fsm；其余 3 步 `both_model_paths_unavailable`→fsm fallback |

## 分类（按协议）
**DEGRADED_HYBRID**：hybrid 可运行，但 fast 端点不可用（`FLEXCELL_JEV_ENDPOINT` 未配置，`clef-flash-q8_0` 权重不可得），
slow 端点也未配置，router 对每一步都记录 `both_model_paths_unavailable` 并回退到 FSM。

## 这个结果能说明什么 / 不能说明什么
- **能**：hybrid 在缺模型时是安全降级的（任务仍 PASS，且记录明确失败原因）；
- **不能**：不能说明分层路由的价值（没有 fast 命中、没有 paid 调用、没有成本/延迟对比）；
- 因此 **不写**"hybrid 更差/更好"，只记 **INFRA_BLOCKED**（对假设而言）。

```bash
python3 setup/acceptance/b2_hybrid_vs_fsm_20261109/verify.py
```
