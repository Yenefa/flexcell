# W5-E2 — 真实 Gazebo 自改进，3 次试点（均**失败**，**BLOCKED**）

| pilot | success | iters | tokens | 改 config | 目标门 | 回归门 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ❌ | 4 | 8235 | 否 | ROBOT_FAILURE | PASS |
| 2（+edit_file、迭代提示） | ❌ | 4 | 8709 | 否 | ROBOT_FAILURE | PASS |
| 3（+消息级记录） | ❌ | 4 | 7500 | 否 | ROBOT_FAILURE | PASS |

## 归因（pilot 3 的 transcript 证据）
- **agent 已正确诊断**：迭代 3 文本明确写出 "zone_2 at (0.45,0.05) has reach ≈ 0.4528 m — out of reach"；
- 之后去"check the gate"，`read_file("gate")` 抛 `PermissionError`（目录），把它带偏；
- 修复后（`read_file` 支持目录 + `list_dir`）再次重跑：agent 仍把 4 轮全部用于探索（config→task.md→gate→acceptance.py），**没有一次 write/edit**；
- **预算耗尽**：4 轮不足以完成"探索 + 定位 + 写入 + 验证"。

## 判定：**BLOCKED**
预注册规定 ≤3 次迭代；实际已用 4 轮仍不足。继续加预算或改提示会改变协议口径，
故按规则停止，不把 PARTIAL 报告成 SUCCESS。

## 后续可选（需重新预注册，不得直接改）
1. W5-E2b：预算 6 轮 + 任务说明"gate/ 只读、无需阅读"，并预注册；
2. 或改为"合成层成功、真实层待办"，等更强的模型/工具形态再测。

## 记录
- `pilot1-*`、`pilot2/`、`pilot3/`（含 `transcript.md`）；
- 三次均保留失败，不删除。
