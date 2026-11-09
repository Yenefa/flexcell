# C9 — 2 cm 容差 dual_object，9/臂（C8 3+3 + 新增 6+6）

协议：[`docs/C9_PREREGISTRATION.md`](../../../docs/C9_PREREGISTRATION.md)（运行前冻结）。

| 指标 | FSM | MTC |
| --- | --- | --- |
| 成功 | **9/9** | **6/9** |
| 平均 wall | 28.281 s | 41.194 s（含失败） |
| 中位 wall | 28.362 s | 33.317 s |

## 失败（全部为 MTC）
- mtc-b：`ERR_RECOVERY_EXHAUSTED`（wall 54.436s）
- mtc-f：`ERR_RECOVERY_EXHAUSTED`（wall 54.399s）
- mtc-m：`ERR_RECOVERY_EXHAUSTED`（wall 54.344s）

失败机制与 C8 相同：`PICK_B(attempt=1):FAIL:ERR_MOTION_FAILED` → `RECOVERY` → 第二次抓取失败 → `BUDGET_EXHAUSTED`。

## 判读（按预注册）
- 方向在 n=9 下持续（C8 的 1/3 → 6/9），但 **Fisher p≈0.206 不显著**；
- Fisher 精确检验（9/9 vs 6/9，18 次中 15 成功）：**双侧 p≈0.206（不显著）**；
- 按协议仍**不宣称因果**：失败集中在 `PICK_B` 运动，机制未归因到 orchestration 本身；
- 单场景、单模型（无 LLM）、仿真（M3-S）；与 C4（默认容差）不可混算。

```bash
python3 setup/acceptance/c9_strict_dual_n9_20261109/verify.py
```
