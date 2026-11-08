# B2 校准 + fast 臂试点（2026-11-09）

## 做了什么
1. **采集**：51 条真实 decision（E-021 归档输入 × DeepSeek-flash），标签 = `FSM_ACTION_AGREEMENT`；
2. **校准**：10 分箱 Wilson 下界；[0.9,1.0] bin：n=51、一致 51、Wilson 下界 **0.929953 ≥ 0.85**；
3. **B2b 运行**：真实 Gazebo，`--decision-policy hybrid --hybrid-threshold 0.85`，校准 + 远端 fast 臂（OpenAI 兼容）；`jev_backend` 临时改为 `local`（实验后已恢复）。

## B2b 结果（`b2b-run/`）
| 项 | 值 |
| --- | --- |
| run status | **PASS / OUTCOME_SUCCEEDED** |
| 任务 wall | **18.372 s**（对照 FSM 14.5 s，+3.9 s ≈ +27%） |
| 路由 | step1 bootstrap→fsm；step2–4 **source=jev**，`escalated=false`，无失败 |
| fast 置信度 | reported **0.99** → calibrated **0.929953**（≥0.85） |
| fast token | 1258 / 1288 / 1416（合计 3962） |
| decide 延迟 | 1111 / 1279 / 1907 ms（远端往返） |
| fingerprint | `fdc81ed9…` |

## 边界（重要）
- **n=1**：只能证明"fast 臂可被真实路由并成功执行"，不能比较成功率；
- 校准标签是 **FSM 一致率**，不是物理成功率；
- `model_sha256` 是**远端身份摘要**（endpoint|model|prompt surface），**不是权重摘要**；
- 校准仅对 τ=0.85 有效（低于 0.9 的置信度尚无样本）；
- fast 延迟 1.1–1.9 s/decision，这正是 Track B 要量化的成本。

```bash
python3 setup/acceptance/b2_calibration_20261109/b2b_verify.py
```
