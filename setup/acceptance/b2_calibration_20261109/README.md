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

---

## 覆盖扩展与离线验证（2026-11-09 第二轮）

### 采集 N=120
- 实际 102 条（18 条因 FSM grammar 无法标注而跳过，计数保留）；
- **101/102 与 FSM 一致**（99.0%），首次出现 1 条不一致（`OBSERVE` vs FSM `ABORT`，confidence 0.9）；
- 置信度分布：**[0.9,1.0] 共 102 条**（98 条 0.9x、4 条 1.0），**0.6–0.9 无样本**。

### 新校准产物 `calibration-n102.json`
- 身份与 n51 完全一致（`prompt_sha256` / `model_sha256` 相同）；
- bin [0.9,1.0]：n=**102**、agree 101、Wilson 下界 **0.946542**；
- 结论：覆盖范围仍只有高置信度区，**不能**在不低于 0.9 的 τ 上声称校准有效。

### 离线验证 `validation-n102.json`
- 确定性切分：偶数索引 fit（51 条），奇数索引 test（51 条）；
- fit bin：n=51、agree 51、Wilson 0.929953；
- test：51/51 路由到 fast、0 escalate；**50/51 一致（98.04%）**，1 个错误；
- 平均 bin 绝对误差 0.0196；
- 说明：标签是 FSM 一致率，不是物理成功率；此验证只检查产物与路由，不产生新的机器人证据。

### 边界与下一步
- 0.6–0.9 分箱需要**低置信度输入**；当前归档输入上模型始终 ≥0.9；
- 若要覆盖低置信区，需要构造决策歧义/边界状态（未来工作，不得伪造样本）；
- 现有产物可用于 τ ≤ 0.9 的路由，B2c 使用的 n51 产物保持可复现。
