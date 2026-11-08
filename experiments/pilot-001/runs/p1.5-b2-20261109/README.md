# P1.5 — B2 诊断级验证臂（合成层，1 次/任务）

`read_diagnosis` 在 verdict 基础上给出：`cause`（reachability/overshoot/contract）、`limits`、`failed_stage`、`suggested_action`。

| 任务 | B2 成功 | 轮数 | tokens | 对照：B（n=3） |
| --- | --- | --- | --- | --- |
| T-A v3 | 0/1 | 6 | 6568 | 2/3 |
| T-B v1 | 0/1 | 6 | 6097 | 3/3 |
| T-C v1 | 1/1 | 5 | 8113 | 3/3 |

## 探索性结论
- B2 **没有**比 B 更好，反而更差；可能与"诊断信息与 telemetry 重复 + 额外工具调用"有关；
- n=1/任务，不能作结论；若继续，应至少 3 次/任务并检查调用序列；
- 与 P1.2 的 B−C=0 一致：目前没有证据表明"结构化验证/归因"带来额外成功率。
