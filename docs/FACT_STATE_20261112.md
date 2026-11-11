# EvoBot — Unified Fact State (Lead, 2026-11-12 round)

> Required by Master Goal §0.3. Every row carries a state from
> `CONFIRMED / INVALID / SUPERSEDED / NOT_RUN / BLOCKED / UNKNOWN` and a source.
> Nothing here is inherited from a handoff document; each row was re-derived from
> the artifact or re-run this round.

**Round authority:** `docs/EVOBOT_MASTER_GOAL_20261112.md` (verbatim copy, sha256
`88E2AB6C…B373`). Higher authority remains `docs/EVOBOT_NORTH_STAR_MISSION.md`.
§8–§14 of that file are still truncated → **BLOCKED_MISSION_TEXT_MISSING**; nothing
here infers their content.

---

## 1. Repository

| Fact | State | Source |
| --- | --- | --- |
| HEAD | `ec4b2080` — **CONFIRMED** | `git rev-parse HEAD`, Windows side |
| Branch | `autonomous/flexcell-remediation` — CONFIRMED | `git branch --show-current` |
| Worktree clean | 1 untracked file (`docs/HANDOFF_20261112.md`), 0 modified — CONFIRMED | `git status --porcelain -uall` |
| Pushed | `origin/autonomous/flexcell-remediation` == HEAD, 0 ahead — CONFIRMED | `git rev-list --count origin/…..HEAD` |
| Master Goal reference HEAD `b3f2664` | **SUPERSEDED** — HEAD has moved far past it | goal §0.1 vs `git log` |
| WSL access to git | **INVALID** — `.git` is a pointer file with a Windows absolute path; every WSL git call fails and *silently reads as "no diff"* | reproduced this round: `fatal: not a git repository … /C:/Users/…` |
| Remote repo | `https://github.com/Yenefa/flexcell.git` — CONFIRMED | goal §0.1 |

**Rule derived:** all git operations go through the Windows shell. A WSL git failure must never
be read as "the file is unchanged".

---

## 2. Frozen artifacts — verified untouched

| Artifact | State | How checked |
| --- | --- | --- |
| `benchmark/evaluators/evaluate.py` push clauses | **CONFIRMED unchanged** — defaults still `min 0.030 / max 0.150 / max_vertical 0.020 / min_cos 0.9`; zone radius from spec `0.06` | `grep` of the file, lines 183–210 |
| `evaluate.py` version | `0.5.0` — CONFIRMED | `EVALUATOR_VERSION = "0.5.0"`, line 20 |
| `evaluate_v0.3.0.FROZEN.py` | exists at `setup/acceptance/evobot_audit_p0_fixes_20261111/`, **not** in `benchmark/evaluators/` — CONFIRMED | filesystem |
| `contracts/push.py`, `push_server.py`, `place_server.py` | 0 lines changed in `93d8168a..HEAD` — CONFIRMED | `git diff --name-only` over the range |
| `sim_profile.py` | not modified this round — CONFIRMED | same diff |
| T08 task specs (dev 2000–2002, unseen 3000–3002) | present, unmodified — CONFIRMED | `benchmark/tasks/t08_*` |

---

## 3. Test-suite reality (re-run this round, not quoted)

| Suite | Documented expectation | **Actual** | State |
| --- | --- | --- | --- |
| `benchmark/evidence/` | `INTEGRATION_PROCEDURE.md` step 1 says **73 passed**; `CAPABILITY_REPORT` says **75** | **75 passed** in 11.7 s | CONFIRMED 75; the 73 in the procedure doc is **INVALID as a number** |
| `test_evaluator_integration.py` | procedure step 2 says **8 passed** | **10 passed** in 1.8 s | CONFIRMED 10; the 8 is **INVALID as a number** |

**Why this matters and is not pedantry:** the procedure is the document an operator follows to
decide whether the evidence chain still works. It states two stale counts. A future operator who
sees 75 where the doc says 73 cannot tell "tests were added" from "tests were silently changed",
and one who sees 73 where it says 75 will suspect a regression that did not happen. Recorded as a
documentation-integrity defect, not fixed in this row (the procedure file belongs to the verifier
acceptance dir).

---

## 4. T08 Push — the round's central capability question

| Fact | State | Source |
| --- | --- | --- |
| T08 executed in real Gazebo at all | **CONFIRMED** — multiple real runs | `evobot_t08_first_push_20261112/`, `evobot_t08_saturation_diagnosis_20261112/` |
| Single-shot baseline, contact height 0.030 | 0.59 mm, contact never established | `HEIGHT_SWEEP_RESULT.md` |
| Single-shot baseline, contact height **0.0200** | **2/5 terminal pass**; displacements 32.63 / 137.84 / 57.71 / 5.05 / 2.63 mm | `saturation_diagnosis/evidence/repeats.tsv` + `evobot_t08_repeats.sh:49` (confirms `contact_height_m = 0.0200`) |
| Closed-loop recovery, same contact height 0.0200 | **4/5 terminal pass**; 73.95 / 90.60 / 145.58 / 97.45 / 122.67 mm | `push_recover_20261112/evidence_v2/recovery.tsv` |
| Fairness of that comparison | **CONFIRMED fair** — identical task instance, identical contact height, identical evaluator; the only difference is the retry policy | both TSVs + the baseline script's literal value |
| `passed` (full 9-gate) for any T08 run | **NOT_RUN / always false** — driver supplies trajectory only, no contact/joint/telemetry bundle | `verdict_t*.json`: `"failure_reason": "no evidence bundle was supplied…"` |
| Statistical significance of 2/5 → 4/5 | **NOT SIGNIFICANT** — Fisher exact two-sided **p = 0.5238**; Wilson95 [0.376,0.964] vs [0.118,0.769]; n≈22/arm needed | `setup/acceptance/evobot_lead_statistical_audit_20261112/` |
| Ceiling risk in the recovery arm | **CONFIRMED RISK** — max 145.58 mm against the frozen 150 mm ceiling = 4.4 mm margin; a fixed-step control already produced 156.77 mm | audit doc §3 + `FIXEDSTEP_CONTROL_RESULT.md` |
| T08 unseen instances 3000–3002 | **NOT_RUN** — zero runs | `benchmark/tasks/t08_unseen/` |
| T08 as a usable robot capability | **NOT ACQUIRED** | `passed` false everywhere; unseen unrun; mechanism of the variance UNKNOWN |

### 4.0 The verifier itself is not fail-closed against a fabricating producer

Found by the independent validation lane and **re-verified by the Lead against the source** this round.
This is the most consequential finding of the round, because it decides whether *any* T08 `passed=true`
can be trusted.

| # | Defect | Verified at | Effect |
| --- | --- | --- | --- |
| 1 | `rest_height_m` is an **operator argument** to the recorder, never bound to the task spec | `recorder.py:264`; `schema.py:76` only checks `_finite()` | `table_support` (`verify.py:141-143`) and `no_lift` (`verify.py:209`) both subtract the *self-declared* rest → a bundle that declares rest = its own height makes both gates vacuous |
| 2 | Demonstrated bypass | auditor fixture: object carried at a **constant 50 mm above the table**, never touching it, `rest_height_m = 0.0675` declared | **`passed=true`, `physical_outcome=PUSHED`, `failed_gates=[]`** — precisely the carry-as-push T08 exists to forbid |
| 3 | `evaluate.py` trusts `observation.trajectory[name].max_z_m` as supplied | `evaluate.py:227-238` | a fabricated `max_z` defeats the terminal lift check independently of the bundle |
| 4 | `observe_from_run.strip_diagnostics` drops `trajectory` and `evidence` | `observe_from_run.py:147-150` (keep-set = objects, move_sequence, agent_claimed_success, agent_claim_source, visits) | a run graded through the real bridge **always** loses its evidence → the honest production path cannot currently reach `passed=true` at all |
| 5 | Bundle not bound to the trial | no `run_id`/nonce comparison; `bundle_sha256` never recomputed (`schema.py:279` is `isinstance(str)`); execution window never used to filter samples | one captured bundle **replayed across 5 trials with different final poses → `passed=true` all 5**; bundle shifted 4.8 m in y still passes |
| 6 | `max_gap_ns` is a tautology | `recorder.py:172` writes `max(gap,1)` = the observed gap; `schema.py:164` compares the gap to itself | 40 of 80 physics steps lost (a 200 ms hole) → `dropped=0`, no schema problem |

**Correct framing:** the verifier **is** fail-closed against an *honest but broken* recorder, and it
**is not** fail-closed against a *fabricating producer*. Every gate that rests on a self-declared
reference value (`rest_height_m`, `pusher_links`, `max_z_m`, `bundle_sha256`, `max_gap_ns`,
`dropped_samples`) is currently vacuous.

**Consequence for this round's numbers:** no T08 `passed=true` may be reported until the bundle's
`rest_height_m` is independently bound to the spec. The existing T08 results are unaffected in the
direction that matters — they are all `passed=false`, so no false capability was claimed — but the
*verifier* cannot yet be used to certify anything. This is a **BLOCKED** state for the acceptance
path, not a robot capability result.

**Fix path decided:** a new version, not an edit — `verify.py` **v1.1.0** (v1.0.0 left byte-identical)
plus an opt-in `evaluate.py` **v0.6.0**, with a migration note stating which historical results keep
their v1.0.0 verdict. This mirrors how `evaluate_v0.3.0.FROZEN.py` was preserved. Requires human
approval before merge because it changes the acceptance protocol.

### 4.1 What may and may not be said about the 2/5 → 4/5 result

| Statement | Verdict |
| --- | --- |
| The terminal-clause pass count went 2/5 → 4/5 on one dev instance | ✅ raw observation (with n=5, p=0.52 stated) |
| Recovery fixes the near-zero-displacement tail (floor 2.6 → 74.0 mm) | ✅ distributional, visible in the data |
| Recovery raises the T08 success rate | ❌ not supported at this n |
| T08 is solved / Independently Verified / Generalization Tested | ❌ |

---

## 5. Baselines A / A′ / B / C / D

| Group | State | Evidence |
| --- | --- | --- |
| **A** (deterministic executor) | **CONFIRMED** A-v2 = 71/72 = 98.6 %, False Success 0 | `evobot_a_v2_final_20261111/` |
| A-v0's 44/72 | **INVALID as a capability measure** — process leak (136 orphans, `load_after` 2.48→19.89) | `PROJECT_STATUS.md`, retraction recorded |
| **A′** (rule planner, no LLM) | **CONFIRMED** 72/72 at plan level on T01–T06 | `evobot_rule_saturation_t01_t06_20261111/` |
| A′ 72/72 meaning | **Known negative result**: rules were written *after* seeing the templates; this proves a 6-rule regex matches the LLM on these templates, **not** generalisation | same doc |
| **B** v1 | CONFIRMED, n=1, real Gazebo, PASS — **SUPERSEDED** | `evobot_t01_baseline_b_20261111/` |
| **B** v2 plan level | 17/18 planned, 17/17 plan-correct — CONFIRMED | `evobot_baseline_b_v2_20261111/` |
| **B** real execution | **CONFIRMED this round**: 9/9 instances executed in Gazebo and passed independently, False Success 0 | `evobot_p0_paired_20261112/README.md` §2 |
| **A′ vs B** paired comparison | **MISLABELLED — the "A′" column is the ORACLE.** `evobot_batch_v2_gated.sh` → `evobot_run_b.sh:31` → `build_composite_plan.py:44` → `baseline_a_composite.plan_from_spec`, which reads `expected_goal`. Regenerating with that builder reproduces the archived plan **byte-identically**; the real rule planner produces a *different* plan on T06 (2 hops vs 1). So the 12-identical/5-different table is **oracle-A vs B**, and the goal §6.4 A′/B gate is **NOT closed**. | `setup/acceptance/evobot_p0_aprime_mislabel_20261112/README.md` (three reproductions) |
| What the paired table still validly shows | Oracle-A and B agree on all 9 executed outcomes; B is not worse than open-book execution on these instances — **CONFIRMED**, but near-tautological since the oracle reads the answer | same |
| Genuine A′/B paired **execution** | **NOT_RUN** — task-6 assigned; requires running A′ plans through RunComposite | `team_task_list` task-6 |
| **C** (self-evolving) | **NOT_RUN as a closed loop** — experience store + diagnosis + retrieval exist with offline tests, never executed in Gazebo as a full event chain | `PROJECT_STATUS.md`, capability report §5 |
| **D** | **UNKNOWN — undefined**; the goal §7.5 gives a *proposed* definition only, explicitly not frozen | goal §7.5, capability report §5 |

### 5.1 The one integrity question left open in P0

`T04-train-seed1000`: executor `outcome=1 (FAILED)`, independent verifier `passed=True`.
Skill reported `ERR_PLACE_FAILED(25)` with `gripper did not open, position=-0.011 requested=0.02`,
executor reported 62. **This is a False Failure at minimum; the cause is UNKNOWN.** Assigned to a
diagnosis lane this round. Until resolved, B's 9/9 may not be quoted without this caveat.

---

## 6. Development Skills (Skill Curator)

| Fact | State | Source |
| --- | --- | --- |
| Four skills registered | CONFIRMED — `ros2-interface-preflight`, `simulation-process-lifecycle`, `evidence-level-audit`, `effect-verification` | `development_skills/registry.json` |
| Any of them VERIFIED | **NO — all four PROPOSED** | same |
| Round-1 revisit verdict | **NO VALID EFFECT EVIDENCE** — the clean runs were confounded (already-fixed driver), no with/without comparison existed, and "zero orphans while idle" measures nothing | `REVISIT_20261112.md` |
| Curator as a real role | CONFIRMED this round — a dedicated teammate exists; the earlier "blocked by team limit" note is **SUPERSEDED** | `list_agents` |
| Development Skill → robot capability | **must not be conflated** — no Development Skill has ever been shown to raise a robot task success rate | goal §1.2 |

---

## 7. Resources, locks, budget

| Fact | State | Source |
| --- | --- | --- |
| Gazebo running at round start | **CONFIRMED none** | `pgrep -af '[g]z sim'` empty; WSL loadavg 0.40 |
| Orphan ROS processes at round start | **CONFIRMED none** of `parameter_bridge` / `robot_state_publisher` / `composite_server` | same probe |
| ROS 2 Jazzy present | CONFIRMED `/opt/ros/jazzy` | WSL probe |
| WSL host | `Ubuntu-24.04`, user `ros`, 12 cores, 15 GB RAM | WSL probe |
| Sim resource lock | **single-simulation rule enforced by the sim lane via `flock`**; pre-existing scripts also refuse to start when another `gz sim` is up | `evobot_t08_evidence_run.sh` guard |
| Dangerous `pkill -9 -f "[$n]"` idiom | **CONFIRMED GONE from every live script** — a repo-wide search finds it only in *documentation* (SKILL.md, README, this fact table, the goal text) and in the explanatory comment of the fixed script. The fixed variant refuses wide patterns by hit-count. | `grep -SimpleMatch '[$n]'` over all `.sh`/`.md`: only doc hits, no executable hit |
| Residual `pkill -f` without a hit-count guard | **CONFIRMED present, low severity** — `scripts/50_start_detached.sh:5` kills `gz sim|move_group|rviz2|ros2 launch` name-wide. It is a dev convenience script, not a benchmark driver, and it does not run under the sim lane. Registered, not blocking. | `scripts/50_start_detached.sh` |
| LLM budget entry point | `ci-public-window/scripts/evobot_llm_key.sh` — exists only in the **main checkout**, not in `wt-comp` | filesystem |
| Paid model calls this round | **0** | no key was sourced |
| Model version recorded | **UNKNOWN for B v2 plans** — cost logged as 14,643 tokens, model id not pinned in the artifact read | `plan_level_check.json` |

---

## 8. What this round must therefore answer

| # | Question | Why it is the highest-value one |
| --- | --- | --- |
| 1 | Can a T08 run produce `passed=true` at all, with a complete bundle? | Until then every T08 number is terminal-geometry only, and the fail-closed verifier is unexercised on a passing case |
| 2 | Does the 4/5 hold on frozen unseen instances? | The only way to tell a skill from a coincidence; currently NOT_RUN |
| 3 | Is the 9-gate verifier actually unbypassable? | A verifier that admits a carry-as-push would invalidate the entire T08 line |
| 4 | What caused T04's executor/verifier disagreement? | Decides whether B's 9/9 is 9/9 or 8/9 with one False Failure |
| 5 | Did any Development Skill measurably help this round? | The Curator's only defensible promotion criterion |

---

## 9. Standing prohibitions (unchanged)

No threshold lowering · no deleting failure evidence · no frozen-file edits · no main merge ·
no PR · no real hardware · no unsanctioned spend · no bypassing the LLM budget gate ·
no quoting a plan-level result as an execution result · no quoting a sim result as a
real-robot result · no single-arm result presented as dual-arm or cross-embodiment ·
LIBERO (Panda) never folded into OpenMANIPULATOR-X capability.
