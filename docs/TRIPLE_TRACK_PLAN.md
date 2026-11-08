# 三 Track 研发计划（Mission Amendment）

> 依 2026-11-09 指令：A（开发）、B（混合运行时）、C（任务编排）**并行长期维持**；
> 任一 Track 不得因其他 Track 进展而被标记完成或移出研究计划。
> 每次自主规划都检查三 Track 的 Milestone / Queue / Gates / Evidence / Blocker / Next。

## Track A — Autonomous Robot Development

**Milestone**
- A0 ✅ 实验 harness（P1.0，5 夹具 + CI）。
- A1 ✅ 真实 LLM 接入（P1.1）。
- A2 ✅ 合成层对照矩阵（P1.2，27 次；C−A p=0.0023，B−C p=1.0）。
- A3 ✅ 相关工作解释（P1.3）。
- A4 ✅ 真实 Gazebo：T-G1 normal 3/3、T-G3 regrasp 1/1（`runs/p1.4-*`）。
- A5 ✅ T-G3 可靠性：**3/3**（`runs/p1.4-tg3-20261109/`）。

**Task Queue**
1. T-G3 重复 2 次（补 n=3）。
2. 组合类真实任务（composite / dual_object）设计与探测。
3. 合成层与真实层交叉验证（同任务族两层都跑）。

**Acceptance Gates**
- 独立验收器 PASS；证据完整度 1.0；false_success=0；
- 不修改验收器/阈值/世界/契约。

**Evidence**：`experiments/pilot-001/runs/*`（P1.0–P1.4）。

**Blocker**：真实 Gazebo 1–2 分钟/次；组合任务初始失败需确定性设计。

**Next Action**：组合类真实任务设计（composite）；合成层/真实层交叉验证。

---

## Track B — Hybrid Runtime Intelligence（不得标记完成）

**Milestone**
- B0 ✅ E-021 恢复与验证：`verify_recovery`=VERIFIED、`selftest`=6/6、`decision_audit`=CONSISTENT（2026-11-09 复跑，日志见 `setup/acceptance/e021_followup_20261109/`）。
- B1 ✅ E-021 后续资格验证（logic-level）：router 回放 **315/315 一致**（`setup/acceptance/e021_followup_20261109/`）；model replay 与 physical acceptance 仍 BLOCKED。
- B2 ⏳ 混合路由实验（当前端点）与 FSM 对照；B1-B（前瞻 initial_world_state）待实现。
- B3 ⏳ 置信度校准与 τ 扫描扩展。

**Task Queue**
1. 明确 E-021 后续资格的三个缺口并逐条立项：
   - `model_replay` = NOT_RUN（原始 `clef-flash-q8_0` 权重/端点不可得 → 需决定：精确回放不可行时，是否允许"策略输入回放 + 决策一致性代理指标"并标注替代证据）；
   - `physical_acceptance` = NOT_RUN（需真实机器人，当前无硬件 → BLOCKED，不得用仿真冒充）；
   - `initial_world_state` = 0/60 episodes 未记录（协议缺陷，后续运行必须记录；历史数据不可补造）。
2. 设计 B1 资格实验：用已记录的 policy-input replay 跑"决策一致性"代理检验（不依赖原始权重），并预先冻结通过标准。
3. 在仿真窗口用当前模型端点跑 hybrid vs FSM 对照（同世界/预算/阈值冻结）。

**Acceptance Gates**
- 路由 provenance 审计 PASS（315/478 routed、0 gate failures 为历史基线）；
- 成本记账（token/latency/USAGE_SETTLED）完整；
- FSM 控制臂保持不变；
- 任何阈值/协议变更必须在运行前冻结并记录。

**Evidence**：`setup/acceptance/e021_native_recovery_20261024/`、`tau_sweep_desktop_20261005/`、`hybrid_threshold_preflight_20261017/`、`e021_followup_20261109/`。

**Blocker**：原始本地模型权重不可得（远程 paid 提案的权重身份不可审计）；无真实机器人 → `physical_acceptance` 不可完成。

**Next Action**：实现 B1-B（新运行记录 `initial_world_state` 并回放校验），再准备 B2 协议。

---

## Track C — Robotic Task Orchestration

**Milestone**
- C0 ✅ ADR-003：FSM = 控制臂（冻结），MTC = 同一 skill seam 下的 treatment 臂。
- C1 ✅ MTC treatment arm **重新通过资格**：2026-11-09 真实 Gazebo `--skill-backend mtc --case normal` → `PASS / OUTCOME_SUCCEEDED`（`setup/acceptance/mtc_qualification_20261109/`）。
- C2 ✅ MTC 资格重复：**3/3 通过**（同 fingerprint `33b420d1…`，`setup/acceptance/mtc_qualification_20261109/`，`verify.py` = `MTC_QUALIFICATION_N3_PASS`）。
- C3 ✅ FSM vs MTC 同条件对照：协议 `docs/C3_FSM_VS_MTC_PROTOCOL.md`；两臂 **3/3 PASS**，FSM 平均 15.70 s vs MTC 19.30 s（n=3，探索性，无显著性结论）；证据 `setup/acceptance/c3_fsm_vs_mtc_20261109/`。

**Task Queue**
1. ~~C2：MTC 资格再跑 2 次（同配置），确认 n=3。~~ ✅ 已完成（3/3，同指纹）。
2. ~~写并冻结 C3 对照协议~~ ✅ 已冻结并执行。
3. ~~执行 C3~~ ✅ 已完成；下一步 C4：扩大 n 或扩展场景（需重新预注册）。

**Acceptance Gates**
- MTC 严格位于 Task Executor 之下，不接触 Decision/WorldState/action menu（ADR-003）；
- 不得把 MTC 变成第二个 DecisionPolicy；
- 不得为让 MTC 更优修改评估标准；
- 失败记录必须保留（历史两次拒绝即为先例）。

**Evidence**：`setup/acceptance/mtc_qualification_20261109/`、`mtc_first_attempt_20261030/`、`mtc_main_failure_20261030/`、`legacy_parity_20261031/`。

**Blocker**：C3 需要先冻结协议；MTC 运行成本较高。

**Next Action**：C4 设计（扩 n 或换场景；先预注册），并保持 MTC 资格回归。

---

## 调度规则

1. 每轮规划必须读取三 Track 的状态，并在报告中各写一行状态。
2. 资源优先级可依依赖调整，但**不得**以"某 Track 进展快"为由关闭其他 Track。
3. 任何 Track 的"完成/终止"只能来自：合法实验完成、假设被否定、或出现明确替代证据，并写入各自 Evidence。
