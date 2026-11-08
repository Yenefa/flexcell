# E-021 后续资格（B1）— 2026-11-09

协议：[`docs/B1_E021_FOLLOWUP_PROTOCOL.md`](../../../docs/B1_E021_FOLLOWUP_PROTOCOL.md)（先冻结后执行）。

## B1-A ✅ Router 逻辑回放（logic-level）

用**当前** `HybridRouter` 规则，从每个 decision 已记录的 proposal 置信度、阈值与校准标志**离线重算**路由，再与 trace 记录比较。

```bash
python3 setup/acceptance/e021_followup_20261109/router_replay.py
```

| 项 | 值 |
| --- | --- |
| episodes | 60 |
| decisions | 315 |
| 一致 | **315 / 315（100%）** |
| 不一致 | **0** |
| 按 source | fsm 40 / jev 244 / llm 31 |
| fast proposals | 275 |
| paid proposals | 31 |

结果与 `decision_audit.py` 的 315 routed / 275 fast / 31 paid 完全一致；
输出落盘：`router_replay.json`。

## 边界（重要）
- 这是**逻辑级**回放：证明"当前 router 规则能解释全部历史决策"，
- **不是** model replay：原始 `clef-flash-q8_0` 权重与 paid 端点不可得 → `model_replay` 仍 **BLOCKED**；
- `physical_acceptance` 仍 **BLOCKED**（无真实机器人）；
- `initial_world_state`：60/60 历史 episode 均为 `null`（协议缺陷，不可补造）→ B1-B 只做前瞻要求。

## B1-B ⏳ 前瞻记录
后续新运行必须记录 `initial_world_state`（canonical + sha256）；尚未实现。
