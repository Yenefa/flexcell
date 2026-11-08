# B1 协议 — E-021 后续资格验证（冻结草案）

> 背景：E-021 的字节/摘要/来源审计已完成（VERIFIED、6/6、CONSISTENT），但三个缺口仍在：
> `model_replay=NOT_RUN`、`physical_acceptance=NOT_RUN`、`initial_world_state=0/60`。
> 本协议只做**可合法完成**的部分；不可完成的明确标 BLOCKED，不用替代物冒充。

## 1. 目标与不可越过的边界
- **不**伪造 model replay：原始 `clef-flash-q8_0` 权重与端点不可得 → 精确模型回放 **BLOCKED**；
- **不**用仿真冒充 physical acceptance：无真实机器人 → **BLOCKED**；
- 允许做**逻辑级回放**（router logic replay）：用已记录的 `policy_trace` 输入重建路由决策，检验 router 代码与历史一致性；
- 所有结论必须标注证据等级（byte / logic / model / physical）。

## 2. 实验 B1-A：Router 逻辑回放
**输入**：`setup/acceptance/e021_native_recovery_20261024/episodes/` 中 60 个 hybrid 剧集的 `policy_trace`。

**方法**：对每个 decision，读取 trace 中的 `fast.confidence`、`threshold`、`calibration` 标志，按当前 `HybridRouter` 的路由规则**离线重算**应选路径；与 trace 中记录的 `chosen` 比较。

**通过标准（冻结）**：
- 重算一致率 = **100%**（任何不一致都视为规则漂移或 trace 误解，必须解释）；
- 复算的 routed / fast / paid 计数与 `decision_audit.py` 报告一致（315 / 275 / 31）；
- 不修改任何历史 episode 字节。

**失败处理**：若不一致 > 0，记录差异样本并判定"当前 router 与历史记录不一致"，不得改写历史使其一致。

## 3. 实验 B1-B：前瞻 initial_world_state 记录
**问题**：60/60 历史 episode 未记录 initial WorldState（协议缺陷，无法补造）。

**方法**：后续任何 hybrid/FSM 运行必须记录 initial WorldState（canonical serialization + sha256）；首次实现后，用一次新运行证明字段存在且可回放。

**通过标准**：新运行的 episode 含 `initial_world_state`，其 sha256 可在回放时复算一致。

## 4. 实验 B1-C：模型回放与物理验收（BLOCKED）
- `model_replay`：需要原始本地权重与 endpoint；当前不可得 → **BLOCKED**，记录复现条件；
- `physical_acceptance`：需要真实机器人；当前无硬件 → **BLOCKED**，不得以仿真替代。

## 5. 判读与报告
- B1-A 通过 → 可写"router 逻辑与历史一致（logic-level）"，**不能**写"model replay 通过"；
- B1-B 通过 → 可写"前瞻记录缺陷已修复"；
- B1-C 保持 BLOCKED，直到条件满足；
- 所有结果写入 `setup/acceptance/e021_followup_20261109/`，并更新 `docs/TRIPLE_TRACK_PLAN.md` Track B。

## 6. 冻结声明
- 本协议在 B1-A 运行前提交；通过标准不得事后放宽；
- 若 B1-A 失败，保留差异样本与结论，不修改协议以"通过"。
