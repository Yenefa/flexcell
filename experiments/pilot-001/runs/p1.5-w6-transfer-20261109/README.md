# W6 迁移 — Cold vs Warm，同条件 3+3（2026-11-09）

协议：[`docs/W6_TRANSFER_PREREGISTRATION.md`](../../../docs/W6_TRANSFER_PREREGISTRATION.md)（运行前冻结）。
运行顺序：C, W, W, C, C, W。

## 结果（不含 2 次 pilot）
| run | arm | success | iters | tokens | plan | 是否写 plan |
| --- | --- | --- | --- | --- | --- | --- |
| cold-c1 | cold | ❌ | 5 | 6368 | [0.45,0,0.0175] | 否 |
| warm-w1 | warm | ✅ | 5 | 5889 | [0.25,0,0.0175] | 是 |
| warm-w2 | warm | ✅ | 4 | 4646 | [0.25,0,0.0175] | 是 |
| cold-c2 | cold | ❌ | 5 | 5534 | [0.45,0,0.0175] | 否 |
| cold-c3 | cold | ❌ | 5 | 6344 | [0.45,0,0.0175] | 否 |
| warm-w3 | warm | ❌ | 5 | 5317 | [0.45,0,0.0175] | 否 |

| 指标 | Cold | Warm |
| --- | --- | --- |
| 成功 | **0/3** | **2/3** |
| 写 plan 的次数 | 0/3 | 2/3 |
| 平均 token | 6082 | 5284 |

## 判读（按协议）
- 方向：Warm 成功 2/3 vs Cold 0/3；
- **Cold 的三次都从未写 plan.json**（只读循环耗尽 5 轮预算），不是"改错了值"；
- Warm 成功两次都写入 `0.25`；失败一次（w3）同样未写 plan；
- 迭代次数在成功样本内没有下降（5/4），但 token 略低；
- **n=3，探索性，不宣称显著**；不能写"迁移已证明有效"。

## pilot（协议外，单独记录）
- Warm pilot：4 轮成功；Cold pilot：5 轮失败且未写 plan。
