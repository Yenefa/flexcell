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
| T08 unseen instances 3000–3002 | **NOT_RUN — the harness cannot instantiate them.** The six U trials ran the **dev** world and were graded against unseen geometry. **RETRACTED as a measurement; INVALID_INFRA (Environment).** | `evobot_lead_t08_unseen_20261112/` (retraction + `check_world_poses.py`) |
| Why: spec-vs-world spawn offset | **CONFIRMED** — `sim_profile.py` hard-codes `target_box_a (0.22,0.00)`, `target_box_b (0.20,−0.18)` and takes **no box-pose argument**. Verified in all six `sim/world.sdf`. Offsets: seed3000 31.6 mm, seed3001 **70.7 mm**, seed3002 36.1 mm on a task whose whole band is 30–150 mm | same §1–§2 |
| **SCOPE of that defect — corrected 2026-11-12 (Lead's round-1 wording was too broad)** | **Measured across every spec set: `train` 0/72 affected, `val` 0/36 affected, `held_out/public` 0/36 affected** — they vary the **zone** (which `sim_profile` *does* accept via `zone_2_pose`) and keep the box poses fixed. **Only `t08_dev` (2 of 3: seed2001 63.25 mm, seed2002 53.85 mm) and `t08_unseen` (3 of 3) are affected.** So the earlier held-out result is **NOT** contaminated by this, and the round-1 claim "no task has ever been instantiated at its declared pose" is **WITHDRAWN as too broad** | `evobot_t08_instance_pose_20261112/scan_pose_scope.py` |
| The fix | **IMPLEMENTED + Unit Tested** — `inject_instance_poses.py` rewrites the box `<pose>` in the world **copy** (sim_profile.py byte-identical), refuses on missing model / non-finite pose, and re-reads the file to assert the write landed. 7 tests pass; offline-verified on the 70.7 mm seed3001 case | `evobot_t08_instance_pose_20261112/` |
| Real unseen measurement with poses instantiated | **RUNNING this round** (task-8, sim lane) — this would be the project's **first** genuine generalisation measurement | `team_task_list` task-8 |
| "blue block moved 0.030/0.010/0.050 m" (earlier claim) | **INVALID — the Lead's own error.** Ground truth shows `target_box_b` world motion = **0.000000 m** in all six. The clause distance **is** the spec-vs-world spawn offset, not motion | `check_world_poses.py` output |
| "0/6 unseen" / "T08 fails to generalise" | **RETRACTED / WITHDRAWN — never measured** | same |
| Dev arms R and S | **UNAFFECTED** — seed-2000 spec matches the world exactly (delta 0.000 m), verified on R/t1 and S/t3. S/t3 `passed=true` stands | same §5 |
| Held-out result from earlier rounds (`evobot_heldout_n6_20261111/`) | **UNKNOWN — needs re-check.** If that pipeline instantiates objects the same way, its initial poses may also differ from its specs. **NOT yet checked; must be verified before being quoted again** | flagged, not resolved |
| T08 as a usable robot capability | **NOT ACQUIRED** | `passed` false everywhere; unseen unrun; mechanism of the variance UNKNOWN |

### 4.0d **FIRST T08 `passed=true` IN PROJECT HISTORY** — and it is the single-shot arm

| Fact | State |
| --- | --- |
| `S/t3` passed with a complete same-run bundle | **CONFIRMED** — all 9 gates True, `evidence_status=COMPLETE`, `physical_outcome=PUSHED` |
| It is a genuine push, not a carry | **CONFIRMED by Lead re-derivation**: displacement 117.32 mm in the commanded direction (cos 0.99833), gripper travel **0.0133 mm**, max lift **0.1017 mm**, 0 attachment events, max step 1.63 mm, trajectory last sample matches `gt_after` to **1 µm** |
| Bundle bound to the run | **CONFIRMED** — `run_id t08loop-S-t3`, `rest_height_m 0.0175 == spec 0.0175` (F1/F2 bypass not in play) |
| Arm | **S = single-shot**, one attempt, no recovery |
| Capability level | **Simulation Tested (1 instance, 1/5)** — NOT `SINGLE-INSTANCE SUCCESS`, NOT Independently Verified, NOT Generalization Tested |

**This reverses the previous round's headline.** This batch, with full bundles:

| Arm | terminal | passed |
| --- | --- | --- |
| R (closed-loop recovery) | 1/5 | **0/5** |
| S (single-shot) | 2/5 | **1/5** |

Fisher exact on passed, valid trials only: **p = 1.0000**. On terminal: **p = 1.0000**.
**Neither arm is distinguishable at n=5.** The correct reading is not "recovery is worse" — it is that
**both arms are dominated by run-to-run variance** and last round's 4/5 was itself inside that variance
(the Lead's audit already put 4/5 vs 2/5 at p=0.5238). n≈9.5 per arm would be needed to detect 80 % vs 20 %.

**Dominant failure mode, 9 valid DEV trials:** `FAIL_DIRECTION` **4** (cos < 0, block driven *backwards*),
`FAIL_ZONE`/`FAIL_OVERSHOOT` 2, `FAIL_LIFT` 1, `GATE_GRIPPER` 1, **PASSED 1**.
(The earlier "8 of 15" figure counted the six invalid unseen trials; it is **withdrawn**.)
Mechanism **UNKNOWN**; shape established (contact face not maintained; a retry cannot fix contact geometry,
consistent with R scoring 0/5).

**Incidental evidence FOR the gripper gate**, from real runs rather than a fixture: passing trial travel
**0.0133 mm** vs rejected trials **3.057 mm** and **4.824 mm** — three orders of magnitude of separation.
This partially answers the open calibration question in §4.0b without touching the limit.

### 4.0a The first T08 runs with a complete evidence bundle (sim lane, this round)

These are the first T08 trials where `passed` is a **decidable** question rather than permanently false
for lack of a bundle. All four re-graded independently by the validation lane: **0 disagreements**.

| Trial | terminal | passed | failed gates | reading |
| --- | --- | --- | --- | --- |
| R/t1 | **true** | false | `gripper` | 149.07 mm, cos 0.99999, in zone at 49.07/60 mm, lift 1.82 mm — **every terminal clause passed** |
| R/t2 | false | false | `terminal` | cos **−0.99269** — pushed the wrong way 65 mm |
| R/t3 | false | false | `terminal` | 141 mm, cos 0.9998, in zone — failed **only** on max_lift 7.2 mm vs 5 mm |
| R/t4 | false | false | all 9 | incomplete artifact set — **INVALID_INFRA**, not a robot failure |

**Producer integrity: CONFIRMED.** The sim lane bound `rest_height` to the spec
(`rest_height_from_spec = rest_height_declared_to_recorder = 0.0175`) and recomputed `max_z` from the
raw physics log (3580 samples). So the verifier bypass described in §4.0 is **not** exercised by this
batch.

### 4.0b Adjudication: R/t1's single failing gate is not what the auditor thought

The validation lane reported R/t1 as a probable **false failure** caused by a **units error**
(`0.002 rad` should be `0.040 rad`). The Lead re-derived it from the robot model:

```
open_manipulator_x.urdf: <joint name="gripper_left_joint" type="prismatic">
                         <limit lower="-0.011" upper="0.02"/>
```

The joints are **prismatic** → position is **metres**, so `0.002` already means 2 mm and the units
claim is **REFUTED**. Two real defects do sit underneath, and they are recorded instead:

| # | Defect | Severity |
| --- | --- | --- |
| A | Field `max_aperture_change_rad` carries **metres**; `verify.py:339` reports it back as `limit_rad` | low — a label asserting a unit it does not have |
| B | The gate bounds **travel only** and never tests whether the aperture could **enclose** the object — the property that defines a grasp | **real, false-rejection path** |

Measured from R/t1's own bundle (1666 samples): aperture `[-0.002960, +0.000096]`, i.e. the fingers sat
within ~3 mm of the **closed** stop, max finger gap **0.2 mm**. A 35 mm block cannot be between them at
any sample. Meanwhile the project's own archived `pick.jsonl` records `GRASPED_AT_GOAL` at
`position = −0.00107` — the **same aperture region**. So a 2 mm bound is narrower than the variation
this project's own nominal grasps exhibit, and the bound is **untraceable to any measurement**
(`evaluate.py:328` calls it "calibrated" with no citation).

**Disposition — decided, and it is a decision not to act:** R/t1 keeps `passed=false`. The limit is
**not** raised, the field is **not** renamed, and R/t1 is **not** re-graded as a pass this round.
Converting the round's only `terminal_passed=true` into its headline success, on the strength of a
threshold change made *after* seeing it fail, is precisely the "adjust the acceptance rule to
manufacture success" failure the mission forbids. Correct order is **calibrate, then re-grade**.

**The experiment that settles it (2 Gazebo runs, no model calls):** G1 = a genuine grasp of the 35 mm
block; G2 = the T08 push (have it); G3 = closed-finger sweep with no object. If G1 separates from G2, a
data-justified threshold exists. **If they overlap, aperture travel cannot distinguish grasp from
contact on this robot and the gate needs a different observable — not a different number.**

### 4.0c Limits divergence — **corrected: it is a category error, not just strictness**

R/t3 failed its terminal clause on `max_lift 0.0072 m vs allowed 0.005`. The first reading was
"the terminal layer is stricter than the spec". **That was wrong**, and the validation lane caught its own
patch reproducing the same defect. The correct reading:

| Quantity | Definition | Where used |
| --- | --- | --- |
| `max_vertical_m` = 0.020 | bounds **`dz = end_z − start_z`** (net vertical change) | spec; terminal clause `max_dz` |
| `max_lift_during_m` | bounds **`lift = max_z − start_z`** (peak height, catches lift-and-return) | nowhere in the spec |

**The T08 spec does not declare `max_lift_during_m` at all** (verified: spec push keys are
`min_displacement_m, max_displacement_m, max_vertical_m, direction, min_direction_cosine, zone`).
So `evaluate.py:327` hands `max_vertical_m` to the evidence layer **as if it were
`max_lift_during_m`** — a bound for a *different quantity*, which **relaxes** `no_lift`.
The terminal clause silently falls back to a hardcoded `0.005`.

**Both layers are wrong in opposite directions, and neither has a spec-declared value to use.**
This is a **category error**, not merely a divergence. F13 stays **OPEN** as a task-design question
(the spec should either declare `max_lift_during_m` or document `0.005` as intentional).

### 4.0c-bis Gripper bound: measured false-rejection rate, and why the limit still is not changed

Nine trials carry gripper telemetry (R/t4's bundle is invalid for §3.3, so it has none):

```
S/t3 0.0130 mm PASS | S/t5 0.0270 | R/t2 0.1320 | S/t2 0.2340 | S/t1 0.9700 | R/t5 1.0370 | R/t3 1.2870   (all gate-ok)
R/t1 3.0570 mm GATE-FAIL  terminal_passed=true
S/t4 4.8240 mm GATE-FAIL  terminal_passed=true
```

**2 of 9 exceed the 2 mm bound (22 % false-rejection), and both are terminal-passing trials that the
gripper gate alone killed.** The one clean pass sits **154× below the limit** and **235× below the
smallest exceeding trial**.

**But the distribution is bimodal with a real gap**: seven trials at 0.013–1.287 mm, then 3.057 and
4.824 mm, **with no measurement between 1.287 and 3.057 mm**. A threshold anywhere in that gap would
separate these nine samples — and with zero measurements inside it, **any cut point is a post-hoc choice**.
So the data proves the bound is **too tight** and simultaneously proves it **cannot say what the right
value is**. The limit therefore **stays at 0.002** this round — not because 2 mm is defensible, but
because the alternative would be a number chosen after seeing the failures. The correct response is the
G1/G2/G3 calibration experiment (§4.0b), and the fix may not be a number at all.

R/t3 failed its terminal clause on `max_lift 0.0072 m vs allowed 0.005` while its displacement,
direction and zone all passed. But the spec's own `max_vertical_m` is **0.020**, and
`evaluate.py:327` passes **0.020** to the evidence layer. So the same run is judged against **0.005** in
the terminal layer and **0.020** in the evidence layer — the terminal layer is **stricter than the spec
it is grading**. Three different lift limits are in play across three layers
(`fixtures.py` 0.005, `evaluate.py` 0.020, terminal default 0.005). **CONFIRMED defect.**

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
**is not** fail-closed against a *fabricating producer*.

**Scope of that claim, corrected after independent review.** The Lead's first draft named six
self-declared values. The Curator re-derived it from `verify.py` and the Lead re-verified:
**only 3 of the 9 gates rest on a producer-declared comparand** —
`table_support` and `no_lift` on `rest_height_m`, and `pusher_contact` on `pusher_links`
(each appears twice in `verify.py`; that is the whole footprint). `max_z_m`, `bundle_sha256`,
`max_gap_ns` and `dropped_samples` are read by **no gate at all** (0 occurrences in `verify.py`).
Two consequences follow, and they point in opposite directions:

| Correction | Effect |
| --- | --- |
| Only 3 gates are vulnerable, not 6 | The bypass surface is **narrower** than first reported |
| The redundancy **holds**: `table_support` is two-sided, so re-declaring `rest_height_m` to hide a lift trips it | The F1 carry-bypass needs the *specific* constant-height construction, not any carry — the finding is **narrower and sharper** |
| **But a hole not on the first list:** `manifest.bundle_sha256` is checked only as `isinstance(str)` (`schema.py`) and **no gate verifies the seal** | Zeroing it changes nothing. This is a **separate, real** defect: the manifest claims an integrity guarantee nothing enforces |

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
| A-v2's 72 verdicts under **one** evaluator | **INVALID** — the archive mixes `evaluator_version` **0.2.0 (27)**, **0.3.0 (40)**, **0.4.0 (5)** | `evobot_lead_regression_v050_20261112/README.md` §3 |
| A-v2 **version-robustness** | **CONFIRMED** — re-grading all 72 archived observations with `evaluate.py` v0.5.0 reproduces **72/72 verdicts, 0 disagreements**, including the single T05 failure | same doc §2, `run_regression.sh` (exit 0) |
| **A′** (rule planner, no LLM) | **CONFIRMED** 72/72 at plan level on T01–T06 | `evobot_rule_saturation_t01_t06_20261111/` |
| A′ 72/72 meaning | **Known negative result**: rules were written *after* seeing the templates; this proves a 6-rule regex matches the LLM on these templates, **not** generalisation | same doc |
| **B** v1 | CONFIRMED, n=1, real Gazebo, PASS — **SUPERSEDED** | `evobot_t01_baseline_b_20261111/` |
| **B** v2 plan level | 17/18 planned, 17/17 plan-correct — CONFIRMED | `evobot_baseline_b_v2_20261111/` |
| **B** real execution | **CONFIRMED this round**: 9/9 instances executed in Gazebo and passed independently, False Success 0 | `evobot_p0_paired_20261112/README.md` §2 |
| **A′ vs B** paired comparison | **MISLABELLED — the "A′" column is the ORACLE.** `evobot_batch_v2_gated.sh` → `evobot_run_b.sh:31` → `build_composite_plan.py:44` → `baseline_a_composite.plan_from_spec`, which reads `expected_goal`. Regenerating with that builder reproduces the archived plan **byte-identically**; the real rule planner produces a *different* plan on T06 (2 hops vs 1). So the 12-identical/5-different table is **oracle-A vs B**, and the goal §6.4 A′/B gate is **NOT closed**. | `setup/acceptance/evobot_p0_aprime_mislabel_20261112/README.md` (three reproductions) |
| What the paired table still validly shows | Oracle-A and B agree on all 9 executed outcomes; B is not worse than open-book execution on these instances — **CONFIRMED**, but near-tautological since the oracle reads the answer | same |
| Genuine A′/B paired **execution** | **NOT_RUN** — task-6 assigned; requires running A′ plans through RunComposite | `team_task_list` task-6 |
| **"A′" is ambiguous in this repo** | **CONFIRMED — three distinct implementations** carry the name: `rule_planner_t01_t06.py` (source of the 72/72), generic `rule_planner.py` (**declines 100 % of T01–T06**), and `baseline_a_prime_rules.py` (a third rule set). Different hashes, different behaviour. | `evobot_t08_gate_audit_20261112/PROVENANCE_APRIME_VERIFICATION.md` §4, verified by the Lead |
| `evobot_p0_paired.sh` (the script that claims to produce the paired execution) | **BROKEN — has never run.** Python heredoc block 1 fails to compile (`unexpected indent`, lines 90-91); `bash -n` passes because bash cannot see inside a heredoc; **no `paired.tsv` exists anywhere** | Lead reproduction + auditor §5 |
| A′ 72/72 scope | **PLAN LAYER ONLY, never executed in Gazebo** — must not be quoted as an execution result | `rule_saturation_t01_t06` banner; auditor §4 |
| **C** (self-evolving) | **NOT_RUN as a closed loop** — experience store + diagnosis + retrieval exist with offline tests, never executed in Gazebo as a full event chain | `PROJECT_STATUS.md`, capability report §5 |
| **D** | **UNKNOWN — undefined**; the goal §7.5 gives a *proposed* definition only, explicitly not frozen | goal §7.5, capability report §5 |

### 5.1 The P0 integrity question — **RESOLVED this round** (H1 confirmed, H2 killed)

`T04-train-seed1000`: executor `outcome=1 (FAILED)`, independent verifier `passed=True`.
Skill reported `ERR_PLACE_FAILED(25)`, executor reported 62.

**Discriminating measurement (bit-exact, no sampling):** the object's XY at release and in the final
ground truth are *the same floating-point values* —
`place.jsonl object_before_release = [0.12515345487641943, -0.14727041380856554]` and
`gt_after.json target_box_b = [0.12515345487641943, -0.14727041380856554]`.
**Lateral displacement release→final = 0.000e+0 m (exact zero)**; only Z changed (−7.572 mm, gravity
settle). The goal was already satisfied **1.10 s before** the failure was written.

| Hypothesis | Verdict |
| --- | --- |
| **H1** the object was already placed; the failure is a false negative | **CONFIRMED** |
| **H2** the object arrived incidentally after a genuine mid-episode failure | **KILLED** — H2 requires lateral motion; it is exactly zero |

**Attribution:** State Management (primary) — the skill's success predicate tests **jaw aperture** while
the actual release is performed by the **carry pin**; and it early-returns before recording any physical
outcome, so `box_after`/`place_error_m` are absent. Tooling/Environment (secondary) — benchmark vacuity.
**Explicitly not** Kinematics, Control, Grasp, Planning, Perception, Runtime or Model Reasoning.

**Scope correction to the known P1 defect:** this is **not** the approved P1 signature. `pick.attach_gap_m
= 0.1646 m`, so the box hangs 0.1646 m **below** the end effector and the jaws never held it. The precise
claim is: *the success predicate tests a mechanism that is not the one performing the release* — a
**scope error in one predicate**, not a second bug. **Fix location = `place_server.py`, NOT the
contract** (the contract already exposes `released` and the skill discards it; `native_success()`
re-derives success and must not be weakened; `recovery.py` correctly forbids PLACE retry). **Gated on
human approval — location conclusion only, no edit proposed or made.**

**Rate is UNKNOWN** (n=1). Missing artifact: `pick.jsonl` (`attach_gap_m`/`carry_offset`) for the 9
`HO-*` runs — one re-execution of any `HO-*` instance settles whether the 0.1646 m pin geometry is
universal or whether both mechanisms coexist.

**Metric rule derived (now project-wide):** `false_failure` is **only defined when an agent made a
claim**. It is computed as `passed and not agent_claimed_success` (`evaluate.py:254/344`), so with no
claim it degenerates to `== passed` and reports `true` on **every passing run** regardless of any defect.
It measures claim calibration, not executor correctness, and is meaningful only paired with
`false_success`. Quoting it from a claim-less run is a category error — all 9 B runs report `true`,
including the 8 clean ones.

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

---

## ADDENDUM — round 3 (2026-11-12), supersedes any conflicting row above

| Fact | State | Evidence |
| --- | --- | --- |
| Round 1's "no task ever instantiated at its declared pose" | **SUPERSEDED / WITHDRAWN as too broad.** Measured: train 0/72, val 0/36, held_out/public 0/36 affected; only `t08_dev` 2/3 and `t08_unseen` 3/3 | `evobot_t08_instance_pose_20261112/scan_pose_scope.py` |
| Held-out n6 result contaminated by the pose defect | **INVALID (the worry, not the result)** — all 36 held_out/public specs spawn correctly, so the earlier result is **NOT** contaminated | same |
| Instance-pose fix | **CONFIRMED implemented + unit tested**, 11 tests, 7 refusal paths, `sim_profile.py` byte-identical; proven live by `gt_before == spec` in all 6 unseen trials | `inject_instance_poses.py`, `runs/*/*/t1/instance_poses.json` |
| Zone marker placement | **CONFIRMED implemented** (round-2 lane finding) — spec zones mapped by index, unused markers parked, table-level display z | same tool, 3 dedicated tests |
| "Backwards flick = end effector cannot hold a contact face" | **INVALID** — both candidate mechanisms refuted. Contact height does not separate forward from backward (2.3 mm across the run, 0.1 mm at first touch) | `evobot_lead_contact_mechanism_20261112/` |
| Where the effector actually contacts | **CONFIRMED: the block's TOP EDGE, every trial** — first-contact z 0.0349–0.0350 m = block top; commanded `contact_height_m` 0.0200; offset **+15 mm**; changing command 0.0300→0.0200 moved the contact **0.1 mm** | same + `push.py:215-219,408-414` |
| Why `contact_height_m` does not control contact height | **CONFIRMED by code trace** — it positions the `end_effector_link` frame, which has **no collision geometry**; the finger links sit ~15 mm above it | same |
| First genuine unseen generalisation measurement | **CONFIRMED, n=6: terminal 5/6, task passed 2/6 (Wilson95 [0.097,0.700]), skill-level 0/6** | `evobot_lead_unseen_result_20261112/`, `runs/U*` |
| The two unseen task passes | **CONFIRMED but NOT controlled pushes** — both came from arm motion the skill itself rejected: `ec=36` 63% shove (2.86 mm margin) and `ec=28` contact lost at 30.6 mm followed by a 117 mm overdrive sweep at t=13.5 s (9.01 mm margin) | same, plus block trajectory in `evidence_bundle.json` |
| Backwards flicks on unseen | **0 of 6** (cos 0.989–0.998), versus 4 of 9 on dev — the flick is **pose-dependent contact geometry**, not an arm property | `evobot_lead_unseen_result_20261112/` §4 |
| Gripper gate false-rejection | **CONFIRMED and now joint-largest failure cause** — 4 of 10 terminal-passing T08 trials across both batches stopped by the aperture bound alone | both batches' trial records |
| G1 genuine grasp aperture travel | **CONFIRMED = 11.71 mm** (open 0.010434 → close −0.001272), i.e. **5.9× the 2 mm bound**, and the grasp **succeeded** (lifted the block **97.4 mm**). G3 (no object, full close) = **12.13 mm**. Max observed push travel = **4.824 mm**. So the two populations are separated by a gap **(4.83, 11.70) mm** and a bound anywhere inside it would preserve grasp rejection while clearing all 4 observed false rejections. **NOT APPLIED — needs human approval** | `runs/calib_G1/`, `runs/calib_G3/gripper_calibration.json` |
| The aperture signal can distinguish grasp from no-object | **REFUTED, and the gate's own stated premise is false.** `verify.py:302` justifies the gate as "the fingers stop against the object's width". Measured: closing on the 35 mm block ends at **−0.001272**, closing on nothing at **−0.001692** — **0.42 mm apart**; commanded −0.011, so it drove nearly the full stroke and stopped 9.7 mm short in **both**, with `reached_goal=True` and `stalled=False` in **both**. The fingers never stop against the object; the drive runs out. **The gate measures drive completion, not contact** | `runs/calib_G1`, `runs/calib_G3`, `verify.py:302` |
| Can the bound be fixed by moving the number? | **NO.** On the endpoint measure grasp (11.706 mm) and push (≤4.824 mm) are cleanly separated, but the gate reads **whole-window travel**: G1 31.00 mm vs G3 24.12 mm, **22% apart**. Widening the bound stops the false rejections and still leaves the gate blind to a grasp. Only a different observable fixes it | same |
| The strong observable | **LIFT.** G1 rose **97.4 mm**; every real push this round rose 0.02–2.37 mm; bound 5 mm → two orders of magnitude, no overlap. G1's rise ran with no carry/attach path (`move_to_pose` + `gripper_cmd` only), so it is a **physical** grasp, not the magnetic pin. The bundle already carries `max_z` | `verify.py` bundle fields |
| R/t1 (3.057 mm travel) | **RESOLVED: FALSE REJECTION.** It sits inside the push population and 1.8 mm *below* the smallest genuine grasp. Round 1 marked this UNRESOLVED for lack of a calibration; the calibration now exists. **Verdict recorded, limit NOT changed** | `evobot_lead_gripper_gate_adjudication_20261112/` §R4 |
| `aperture_travel_rad` units | **The NAME is wrong, the VALUE is not.** The joint is prismatic in **metres** (`lower=-0.011 upper=0.02`, and 0.02 is exactly `gripper_open_position`), so the bound 0.002 is 2 mm of travel. This is consistent with round 1's withdrawal of "should be 0.040 rad" — the number was never radians. Frozen; not renamed | `verify.py:338`, URDF |
| **The pick stack grasps 160 mm above the block** | **CONFIRMED, and it independently corroborates the T04 diagnosis.** The first G1 run reused `pick_server`'s grasp target and produced **zero contact, 0.000000 m rise**, because that target is **160 mm above** the block — the stack grasps by magnetic carry. This is the same quantity as T04's `pick.attach_gap_m = 0.1646 m`. Two independent routes to one number | `runs/scripts/gripper_calibration.py` comments, T04 README |
| Unseen per-arm, corrected | **U (closed loop, 3 attempts): terminal 2/3, passed 0/3. U_shot (single shot): terminal 3/3, passed 2/3.** Both passes from the control arm; recovery 0/3. n=3 per arm — no arm-ordering claim | `runs/results.tsv` |
| Freeze drift in the unseen batch | **CONFIRMED drift, CONFIRMED harmless.** The zone-marker fix landed after 5 of 6 trials, so the fingerprint does not verify. Verified by git's own diff, not by assertion: the only removed line in the entire change is the trailing-newline form of `sys.exit(...)`, so the object-placement path is byte-identical, and zone markers are static and collisionless. Fingerprint recorded as broken, **not re-frozen** | `git diff 3cda5cb5..HEAD`, lane README §7 |
| T08 skill-level capability | **NOT ACHIEVED** — 0/6 on unseen, 0/5 dev closed-loop; the primitive has never satisfied its own contract on any batch | both batches |
| Contact-height calibration (task-9) | **NOT_RUN** | task-9 |
| L4 Develop | **NOT CROSSED** | — |

### Round 3 corrections to the Lead's own record

1. **Withdrawn:** "no task in this benchmark has ever been instantiated at its declared pose" — true of 5 T08 specs, not of the benchmark.
2. **Withdrawn:** "the backwards flick is the end effector failing to hold a contact face" — contact geometry does not predict the flick.
3. **Disclosed:** one commit (`59a9d7f5`) accidentally included 145 MB of derived evidence; the next commit compressed and excluded it (`86f78f2d`), and the oversized blobs remain in history because force-pushing a shared branch is worse than the storage cost.
4. **Disclosed:** a test (`never touches a model that is not in the spec`) required narrowing because the zone-marker behaviour changed **on purpose**; the narrowing is documented in the test and the zone behaviour gained 3 tests of its own rather than losing coverage.
5. **Disclosed:** I first read `calib_G1` while the lane was still re-running it and recorded "the grasp lifted 0.000000 m" as a confirmed fact. The final file (1257 samples, not 1171) shows a **97.4 mm lift** — the grasp succeeded. That row was corrected here rather than left standing, and it is a reminder that a file being present is not the same as a run being finished.
6. **Disclosed by the lane, verified by me:** the lane found its own overstatement ("the block continued to slide on its own" — it was struck again: 104 of 465 motion steps in that phase had gripper contact). Same defect class as my 0.000000 m: describing a partly-observed trace as a complete one. Both are now recorded as such.
---

## ADDENDUM — goal round 2 (2026-11-12), supersedes any conflicting row above

| Fact | State | Evidence |
| --- | --- | --- |
| `contact_height_m` positions the contact | **REFUTED.** Six commanded heights from −0.0050 to +0.0200 all give first-contact z = **0.0350**, 6/6, 0.1 mm spread. Fitted slope **0.0001** against a predicted 1.0 | `evobot_lead_contact_calibration_prediction_20261112/`, `evobot_t08_contact_calibration_20261112/runs/` |
| Why the command cannot lower the contact | **CONFIRMED, collision-limited.** `cmd_h + approach_error` converges on the block top: 0.0346, 0.0339, 0.0335, 0.0349 — a 1.4 mm span, all within 1.5 mm of 0.0350, across four independent runs. The finger lands on the block and the arm **stops**; the target below is **unreachable**, not merely ineffective | same |
| Lower commanded heights | **WITHDRAWN as "stalls".** Four of six (H0000, H0050, H0100, HM0050) have `increments_executed=0`, `contact_made=false`, `error_code=30` — they **never pushed**. Their 4.4–5.9 mm "displacement" is the block nudged by the descending arm | `push_00.json` per trial |
| H0150 as "deepest face engagement" | **WITHDRAWN.** Measured against the block's own pose, its contact spans 68 mm of z reaching **43 mm above** a 35 mm block — tumbling contact, not a palm-on-face push | contact logs + block pose |
| The contact frame | **CONFIRMED world frame** (was an unproven assumption). Contact reads 0.0350 = block top, not +0.0175 = local half-height | same |
| The push skill can perform a face push | **NO — structurally blocked.** It must descend through the block's top face to reach the side, so the block physically prevents the approach. Fix is geometry (side-mounted pusher, single finger from the side, or a side approach), never a parameter | this round, 3 independent lines |
| Baseline A-prime | **NOT VACUOUS — my claim was wrong and is withdrawn.** A-prime is **36/36 correct** on T12/T13/T14 (12/12 each, verified independently by me and by the auditor). Those templates exist as first-class generators in `benchmark/generators/unseen_tasks.py`; they are absent only from the task split | `evobot_lead_p0_aprime_vacuity_20261112/` §CORRECTION, `evobot_p0_aprime_independent_20261112/` |
| P0's A-prime-vs-B comparison | **NOT_RUN — and the reason is a pairing defect, not a broken baseline.** B is pointed at T01–T06, A-prime at T12–T14. The baseline is real; the arms were pointed at different template families | same |
| A-prime answer-blindness | **CONFIRMED structurally** — `reduce_to_public` strips the answer keys, and four corruptions of `expected_goal` leave the plan byte-identical. One latent hole: the reducer is applied **conditionally** (`run_baseline_a_prime.py:40-41`), harmless today (0 of 114 specs lack the key) | `check_aprime_blindness.py` |
| The sweep's displacement ordering | **NOT INTERPRETABLE.** n=1 per height and four of six are descents, not pushes | this round |

### Goal round 2 self-corrections

1. **Pre-registered prediction falsified** by 20.1 mm, four times its own stated tolerance — recorded as falsification, not refitted.
2. **"Four heights stall" withdrawn** — they never pushed at all; I had noticed this for one trial and failed to generalise it to three more.
3. **"H0150 = deepest face engagement" withdrawn** — it is tumbling contact; the trial cannot support the claim.
4. **"A-prime is vacuous" withdrawn** — refuted by the independent auditor and confirmed by my own reproduction. The narrower true statement is a template-family mismatch, and the difference changes the remedy from "rewrite the planner" to "run it on its own templates".
5. **Evidence gap in my own analysis, fixed** — the sweep's full per-step contact logs were initially left uncommitted while my corrections were derived from them; now committed as 18 `.jsonl.gz` files so every claim above re-derives from disk.
### Goal round 2, further corrections (append-only; earlier rows stand unless listed here)

| Fact | State | Evidence |
| --- | --- | --- |
| `run_composite` action server missing | **FALSE — RETRACTED.** The server is `task_fsm_server`, which registers `RunComposite` at `task_fsm_server.py:288-293`. I grepped for a *binary named* `composite_server` and concluded the capability was missing. The archive corroborates it: `HO-0dcde4dc0f5a/task.out` carries `run_id: composite-…` and `completed_stage_ids`, produced only by `_execute_composite` | `task_fsm_server.py`, archived `task.out` |
| A-prime execution | **NOT RUN — blocked only by operator kills, not by infrastructure.** Re-authorised | this round |
| Fairness condition 3 (same executor path) | **HOLDS** — B used `RunComposite`, and A-prime's batch targets the same action | archived `task.out` |

**The five premise errors of goal round 2**, all recorded in their artifacts rather than deleted:

| # | Error | Shape | Caught by |
| --- | --- | --- | --- |
| 1 | "four heights stall" | read a value without reading the field that contradicted it | sim lane |
| 2 | "H0150 is face engagement" | read a z-coordinate without reading the block pose | sim lane |
| 3 | "A-prime is vacuous" | enumerated `benchmark/tasks/` and concluded about the repo | independent audit |
| 4 | "the batch died" | matched a process name and concluded about liveness | self, after killing a live run |
| 5 | "the server is missing" | matched a file name and concluded about capability | independent audit |

**#4 and #5 are the same error twice: resolving labels and inferring capabilities.** The corrective now adopted: **resolve the capability, not the label** — ask *who implements `RunComposite`*, not *is there a file named `composite_server`*; ask *what holds the lock* via `fuser`, not *is there a process matching this name*. It would have caught #3 as well.
### Goal round 2, P0 results (append-only)

| Fact | State | Evidence |
| --- | --- | --- |
| A-prime has ever executed a task | **YES — first time in project history, this round.** `HO-0dcde4dc0f5a`: composite `outcome=0`, `error_code=0`, both stages completed, 36 s, **0 model calls** | `evobot_lead_p0_aprime_first_execution_20261112/` |
| A-prime's first execution passed | **CONFIRMED, n=1** — frozen `evaluate.py` v0.5.0, all clauses: `placement:target_box_a`, `placement:target_box_b`, `order` → `passed=True`, `failed_clauses=[]` | same, `grade_first_execution.py` |
| A-prime's executor plan vs B's | **CONFIRMED identical 16/16** on `stages`, `position_tolerance_m`, `clearance_m`, `motion_profile_id`, `initial_objects` — including `spread_destinations` destinations | `evobot_lead_p0_aprime_equivalence_20261112/` |
| A-prime's pass RATE on T14 | **MEASURED: 13/16 evaluation_passed, 9/16 execution_succeeded, all 16 attempted.** B is 14/16 and 11/16. My first published figure was **9/16 and WRONG** — see the next row | `evobot_lead_p0_aprime_first_execution_20261112/grade_all.py` |
| Why 9/16 was wrong | **My grading error, caught by the audit.** I derived A-prime's `move_sequence` from the executor's `completed_stage_ids` while B's came from `observe_from_run` reading `pick.jsonl` — **different recorders per arm**. When the FSM reported `error_code=62` its stage list was short or empty, so `order` failed even on world-correct runs. Corrected to 13/16 using the same observation builder for both arms | same + `evobot_p0_aprime_execution_20261112/grade_final.py` |
| The executor's verdict vs the world's state | **THEY DISAGREE ON ~30% OF RUNS ON BOTH ARMS.** 4 of A-prime's 7 execution failures still pass evaluation. `HO-40348a081df6`: executor `error_code=62` with `completed_stage_ids=[]`, ground truth shows both boxes inside the zone radius. **The FSM said it failed; the world says it did not.** Live defect, planner-independent, wants its own task | same |
| A-prime vs B on T14 | **Within noise — do not rank.** 9 vs 11 on 16 tasks, one template, B from archive not re-run. Defensible: A-prime reaches within two tasks of B at **zero model cost**. Indefensible: any statement about general quality | same |
| B's measurable planning value on T14 | **ZERO** — a zero-cost rule parser reproduces its executable plan 16/16 | same |
| `order` clause graded from a snapshot | **SILENTLY FAILS — harness defect.** It reads `final_state['move_sequence']`; given `{objects}` alone the sequence is empty and the clause fails by construction. I hit this and nearly recorded it as an A-prime failure | `evaluate.py` order clause |

**The general lesson, worth carrying beyond P0:** *a clause that needs a time series must refuse to grade when given a snapshot, not silently fail.* This is the mirror of the vacuous-clause finding — there a clause passed for the wrong reason, here one failed for the wrong reason. Both are the harness, not the robot.
---

## ADDENDUM — goal round 3 (2026-11-12): the False Failure mechanism

| Fact | State | Evidence |
| --- | --- | --- |
| The ~30–37 % false-failure rate on both P0 arms | **ONE DEFECT, root-caused.** `place_server.py:424-432` uses **gripper aperture** as the release predicate: fails when `aperture_error > 0.005` **and** `not reached_goal`, with `gripper_open_position = 0.02` | `evobot_lead_place_release_predicate_20261112/` |
| Why that predicate is wrong on this robot | **CONFIRMED, and the decisive test needs no geometry.** Count the actual pin releases: **releases = 2 → pass (13/13), releases = 1 → fail (3/3) = 16/16 perfect separation.** If the gripper held the box, a gripper that fails to open would *retain* it; it does not. The aperture verdict predicts nothing | independent audit, verified by me |
| The carry offset | **≈ 160 mm, not a single value.** n=29 `start` events: min −167.1, max −155.1, **mean −161.5, spread 12.0 mm**. My earlier "−163.8 mm" was **one sample** and must not be quoted as the offset. Same quantity as T04's `attach_gap_m = 0.1646 m` | `analyse_place_failures.py` |
| The transport mechanism | **CONFIRMED with one limit.** 2642/2642 pins `confirmed:true`, backend `velocity_servo` 102/102, **zero** gripper-contact records in any skill log. **No physics-engine contact trace exists**, so "the fingers never touch the box" rests on the causal test, not on direct contact evidence | independent audit |
| The aperture band is narrower than the actuator's own shortfall | **CONFIRMED.** G1 measured free-space open at **0.0104** against a 0.02 target → `aperture_error = 0.0096 m`, nearly **2× the 0.005 m tolerance**. The check passes only because `reached_goal` rescues it; it is one flag from rejecting every placement | G1 calibration + `place_server.py:68-69` |
| The object is released anyway | **CONFIRMED.** `place` returns `released: false`, while `carry.jsonl` records `{'event':'stop','cause':'release','engaged':true}`. The pin releases on abort and drops the box at the destination — which is why 4 of A-prime's 7 "failures" still pass evaluation | same |
| Frequency | **12 of 63 place attempts (19 %); 12 of 32 runs (37.5 %)** — A-prime 7/16, B 5/16 | `analyse_place_failures.py` |
| Historical reach | **51 of 539 place attempts (9.5 %) across 21 acceptance archives, back to 20261010.** Worst: P0 A-prime 24.1 %, goal-check A/B 16.7 %, pooled n=32 16.7 %, crosstype 14.7 %, unseen n6 14.3 % | sweep of every `place.jsonl` |
| B's "architectural recovery edge" (14/16 → 16/16) | **REFUTED.** Both recovered runs failed their first attempt with **exactly this defect**: `PICK_A(attempt=1):OK, PLACE_A:FAIL, ERR_PLACE_FAILED, legacy_error_code=25`. B's edge is a retry loop around its own place bug, not a capability | `failure_evidence.json` of both runs |
| Who is the better arm | **NOT ESTABLISHED.** Every run separating A-prime (13/16 one-shot) from B (14/16 first, 16/16 with retries) fails for this defect. The comparison cannot distinguish them | same |
| Every **execution-verdict** success rate in project history | **AN UNDERESTIMATE** — the defect sets the floor at ~19 % of place attempts. But see the next row: this is confined to execution verdicts | round 3 |
| **Are the project's RESULTS contaminated?** | **NO — and I nearly claimed otherwise.** Re-graded all 238 archived runs: **47 (19.7 %) hit the release defect, and of the 11 recorded failures among them, ALL 11 are GENUINE** — each has an object still at its initial pose. **Zero provable False Failures.** Task clauses grade final world positions, which are correct, so `independent_evaluation_passed` is **sound**; only `execution_succeeded` is corrupted | `evobot_lead_historical_regrade_20261112/` |
| Why round 3's framing was too broad | "The world is right and the verdict is wrong" holds for the **execution** verdict, not the **task** verdict. 28 of the 47 affected runs were recorded as PASS anyway, so the defect does not determine the verdict on its own. Release is not placement | same |
| The carry mechanism | **never failed to release — 0 stuck carries in 238 runs** (releases = starts everywhere) | same |
| The general lesson | **On this robot, gripper telemetry is not evidence about objects.** The same mistake appears twice: T08's push gate uses aperture travel to detect *a grasp* (refuted round 2), `place` uses aperture position to detect *a release* (refuted now). Both use a gripper-state proxy for an object-level event | both refutations |

### The general rule this round produced, which outranks any single fix

Audit pushback accepted: this is **not one bug in one file**. It is one instance of a pattern — **a
self-declared internal quantity standing in for evidence about the world.** Six instances tabulated:

| # | gate | internal quantity | standing in for | refuted by |
| --- | --- | --- | --- | --- |
| 1 | `place_server` release | gripper aperture | the object was released | this round, 16/16 causal test |
| 2 | T08 push gate | aperture travel | a grasp occurred | round 2, 0.42 mm separation |
| 3 | T08 push gate | `rest_height_m` self-declared | the effector's height | round 2, bypass proven |
| 4 | T08 push gate | `pusher_links` self-declared | which links touched the block | round 2 |
| 5 | `verify.py` gate set | `max_z_m` taken from the producer | the true maximum height | round 2 |
| 6 | `recovery_decision.json` | `failure_class` label | what actually failed | this round: labels a `PLACE` failure `grasp` |

> **A gate may only pass judgement on a quantity it measures itself, and that quantity must be causally
> connected to the thing being judged. A self-report from the component being judged is not evidence
> about the world; it is evidence about the component's opinion of itself.**

Fixing `place_server` alone fixes one instance. The rule implies binding every gate to an observable
causally connected to the outcome, with self-declared values demoted to diagnostics.

Also from the audit: **B's retry re-picks the object** (`pick.jsonl` shows the same object picked twice
in both recovered runs), so it is a full stage re-execution, not a checkpoint resume — and attempt 1 had
**already delivered the box** to within 44 mm of zone centre. The retry picked it *out of* the correct
destination. Recovery did not rescue a task; it undid one.

---

## ADDENDUM — goal round 4 (2026-11-12): the fix was already pre-registered, and its own criteria are broken

| Fact | State | Evidence |
| --- | --- | --- |
| Round 3 presented the `place` release defect as new | **FALSE — I rediscovered 2026-11-11's work.** The mechanism was established with 9 cases in `setup/acceptance/evobot_release_mechanism_20261111/`, the wrong earlier proposal (`bounded_release_retry`) was already superseded, and the correct fix was already **pre-registered and awaiting approval** in `evolution/proposals/release_confirmation_preregistration.json` | both dirs |
| Corrective for the above | **Before diagnosing a defect, search `evolution/proposals/` and the acceptance archive for its signature.** I checked whether the code had the bug and never checked whether the project already knew | — |
| Are the project's task-level RESULTS contaminated by the release defect? | **NO — and I nearly claimed otherwise.** Re-graded 238 archived runs: 47 (19.7 %) hit the defect; of the 11 recorded failures among them, **all 11 are GENUINE** — most with an object still at its initial pose. **Zero provable False Failures.** Only `execution_succeeded` is corrupted; `independent_evaluation_passed` is sound | `evobot_lead_historical_regrade_20261112/` |
| The carry mechanism | **never failed to release — 0 stuck carries in 238 runs** (releases = starts everywhere) | same |
| The pending proposal's task-level prediction | **UNSUPPORTED.** It predicts task-level false failures 6.2 % (2/32) → 0 %, and sets "task-level false failure count falls to 0" as a success criterion. Measured: **0/237**. The criterion is **vacuous** — it is already satisfied and would pass for the wrong reason | `evobot_lead_preregistration_test_20261112/` |
| The pending proposal's safety argument | **FALSE AS WRITTEN.** It says the evaluator grades the world, not the self-report. But `benchmark/evaluators/observe_from_run.py:74,114` reads `place.released`, and that module **builds the observation the evaluator grades**. The changed field is on the grading path | `evobot_lead_fix_prefix_validation_20261112/` |
| Why the fix is nonetheless safe (part 1) | **INCIDENTALLY.** All 51 rows with `released=false` carry **no** `box_after`; 488 released rows do. `observe_from_run` needs a pose *and* a truthy `released`, so those rows are skipped either way. Safety comes from the failure path not writing `box_after` — not from a guarantee | same |
| The risky part is the proposal's own follow-on prediction | **Part 2 (`place_box_after_will_be_recorded`) changes the grading input for 51 rows**, shifting provenance from `verify.jsonl` to `place.box_after`. It is **not covered** by the proposal's safety argument and needs its own regression check. Whether it creates false success is **NOT DEMONSTRATED** — `box_after` does not exist on those rows, so its future value cannot be read offline. Unlikely is not a test | same |
| The pattern behind three separate findings | **A claim that some quantity is not used, made without tracing its use.** Round 2: aperture travel assumed to mean a grasp (0.42 mm from air). Round 3: aperture assumed to mean a release (`carry_release_confirmed` in the same record). Round 4: assumed the evaluator does not read `released` (`observe_from_run.py:74` does). **The cheap check is a grep** | all three |

---

## ADDENDUM — goal round 5 (2026-11-12): P3's improvement chain is not gated

| Fact | State | Evidence |
| --- | --- | --- |
| P3's regression gate | **DISABLED.** `evolution/proposals/run_loop.py:68` calls `regress.gate(proposal, run_regressions=False)` while the gate defaults to `True`. The gate's own docstring calls itself "the guard that makes Baseline C different from let the agent edit code". **A proposal that breaks every verifier is accepted and written** | `evobot_lead_p3_gate_integrity_20261112/` |
| Why it was disabled | **A real reason.** Enabling it: **105 of 109 verifiers pass, 4 fail for pre-existing reasons.** An all-green gate would reject every proposal forever. It was turned off rather than made differential — **so it has never gated anything** | same |
| The capability freeze | **THREE generations, formally re-pinned** (`evobot_capability_freeze_20261111` → `evobot_freeze_change_20261111` → `benchmark/capability_baseline.json`). My first draft claimed a violated freeze; **that was too strong and I withdrew it before publishing**. Drift against a superseded baseline is expected | same |
| The **LIVE** baseline | **exactly ONE drift: `benchmark/evaluators/evaluate.py`** (pinned `c75eaf78…`, actual `441903f1…`). Changed at `4fd36cd6` on 2026-11-12 after the live baseline was recorded, and never updated | same |
| `evobot_capability_freeze_20261111/verify.py` | **validates the OLDEST baseline, superseded twice, never retired** — so it fails permanently on files that are *supposed* to have changed. It is one of the four reasons the gate stays off | same |
| `freeze_check.txt` and `evidence_summary.txt` | **BOTH STALE.** They record `{"baseline": "INTACT", "pinned": 9}` and `verifier failures: 0` while the verifier currently fails. Same pathology as round 3's `released: false` beside `carry_release_confirmed: true` | same |
| **The gate is not read-only** | **108 of 109 `verify.py` write their own `verify_result.json`.** Running the gate rewrites evidence across the acceptance archive. A gate that mutates the evidence it reads cannot certify it unchanged | same |
| A verifier can fail because the world got **better** | **`evobot_p2_feasibility_20261111` is red because commit `0dc1245b` ADDED the push clause** — fixing exactly the deficiency its pre-registration documented ("no displacement/push clause"). Not a regression: a **stale premise** | same |
| The general form of that | **A verifier of the shape "X is currently missing" becomes permanently false the moment X is added, and then blocks every gate that includes it. Premise verifiers need a retirement date, not just a creation date** | — |
| Corrected count of the 4 failures | **2 of 4 are stale records, not live defects** (`capability_freeze`, `p2_feasibility`); the other two (`baseline_a_v0`, `t08_push_criterion`) were not investigated this round → **UNKNOWN** | same |
| `run_loop.py` writes proposals in place | **it overwrote `evolution/proposals/actuator_stall.json`**, a proposal awaiting review. Reverted with `git checkout`. A proposal awaiting human approval can be silently replaced by a regeneration | same |

**Nothing repaired.** No pinned file edited, no re-run performed (a human decision at sanctioned cost), no threshold or spec or verdict changed.

---

## ADDENDUM — goal round 6 (2026-11-12): T08's 0/6 is a REAL capability gap, not a false-rejection artifact

| Fact | State | Evidence |
| --- | --- | --- |
| Hypothesis: T08's 0/6 is mostly a false-rejection artifact, like the `place` defect | **REFUTED.** Graded all 7 unseen push records against **all four** sub-clauses of `evaluate.py`'s push clause. **1 of 7 satisfies the complete criterion**; 6 fail physically (block did not reach the zone, moved the wrong way, or never made contact) | `evobot_lead_t08_false_rejection_test_20261112/` |
| My own first pass on this | **WRONG, and I caught it.** Grading 3 of the 4 sub-clauses gave "8 of 23 satisfy, 6 rejected by the skill" — a 75 % false-rejection rate. I had omitted `evaluate.py:199-210`: the block must **end inside `zone_push`** (radius 0.06). With it: 1 of 7 | same |
| **False Success (T08 unseen)** | **0.** The fail-closed property the mission requires **HOLDS** — the skill never claimed a success it did not achieve. This is the one thing 0/6 was supposed to guarantee, and it is true | same |
| The one genuine false rejection | **`U/seed3002`**: moved 0.1480 m (task band allows ≤ 0.150), ended 0.0294 m from zone centre (inside 0.06), did not lift → **task satisfied**, but the skill reported `ERR_DISPLACEMENT_OVERSHOOT` because it *requested* 0.0900 m and the error (0.0580) exceeded `displacement_tolerance_m` = 0.005 | same |
| The defect shape, third instance | **The skill is stricter than the task, on a different quantity.** Task accepts displacement **in a band [0.030, 0.150]**; skill requires **±5 mm of the requested distance**. #1 T08 gate (aperture travel ≠ grasp), #2 `place` release (aperture ≠ release), #3 T08 verdict (request-error ≠ band membership) | — |
| Magnitude of that third instance | **1 of 7, NOT 6 of 7.** The first two were systematic (37.5 % of runs; 100 % of place failures). Fixing this one moves T08 from 0/7 skill-certified to 1/7, not to 6/7. **Do not cite it as a major false-failure source** | same |
| T08's real blocker | **REACH, not verification.** The block must travel ~0.09–0.11 m into the zone; observed attempts reach 0.014–0.051 m. Same contact-geometry problem the height calibration exposed. **No verdict change fixes it** | same |
| T08 four states (unseen) | `planning_correct` **UNKNOWN** (not re-measured); `execution_succeeded` (push clause only) **1/7**; `independent_evaluation_passed` (whole task) **2/6** from the earlier held-out run — **different denominator, not reconciled**; `agent_claimed_success` **0/7** | same |

**T08 skill-level remains 0/6 by the mission's own skill-level definition.** This round establishes that the number is honest, not that it changed.

---

## ADDENDUM — goal round 7 (2026-11-12): P3's gate is now ON

| Fact | State | Evidence |
| --- | --- | --- |
| P3's regression gate | **RESTORED.** `evolution/validation/gate_differential.py` requires **no NEW** verifier failures versus `known_failures.json` instead of no failures at all. `run_loop.py` now calls it | `evobot_lead_p3_gate_restored_20261112/` |
| End-to-end proof | **109 verifiers run per proposal; 4 known failures unchanged; 0 new**; before the change the loop printed *"structure accepted (regressions skipped by caller)"* | same |
| The gate's own side effect | **SOLVED and verified.** 108 of 109 `verify.py` rewrite their `verify_result.json`; the gate now byte-snapshots the files beside each `verify.py` and restores what its run changed. Restoration proven byte-identical, and **zero `verify_result.json` dirty** after a full loop run | same |
| **My second defect this round** | **I first fixed the side effect with git — and git does not work in this worktree under WSL.** Its `.git` holds a Windows path, so both helpers raised, `_dirty_paths()` returned empty, and **the restore silently did nothing while the gate reported success.** Caught only because a file stayed dirty after a full run. Same failure mode as everything in this file: a component reporting a result it did not achieve | same |
| **My first defect this round** | **My first TEST was wrong, not the gate.** I baselined a verifier, ran a *different* one, and expected a "cleared" note. A baselined failure can only be reported cleared if it was actually run | same |
| Gate evidence level | **Designed → Implemented → Unit Tested (7/7).** **NOT** Simulation Tested, **NOT** Independently Verified. It is test tooling, not robot capability | same |
| Two baselined failures remain `UNKNOWN` | `evobot_baseline_a_v0_20261111` and `evobot_t08_push_criterion_20261111` are recorded in `known_failures.json` so the gate can run, **not** because they are benign. Cause **UNKNOWN** | same |
| **T08's blocker is kinematic, not a verdict problem** | The `move_to_pose` action **does** accept a full `PoseStamped` with orientation, so the wrist attitude is commandable in principle — but the URDF analysis (round 2) puts the palm bodies ~82 mm along link5 x with the arm's reachable floor at the block's top edge (0.035). Reaching the side face at mid-height (0.0175) needs either a different tool or a robot change. **Needs approval; not attempted** | `evobot_lead_contact_mechanism_20261112/` |
| P3 event chain | **STILL INCOMPLETE.** The guard is restored. No change has been applied and re-measured, and the **seven-field experience records with independent review are not delivered.** No round so far has achieved Baseline C end-to-end | — |

---

## ADDENDUM — goal round 8 (2026-11-12): T08 pushed into the zone. Rounds 6–7 were wrong about why it couldn't.

| Fact | State | Evidence |
| --- | --- | --- |
| **My rounds 6–7 conclusion that T08's blocker was reach** | **WRONG — WITHDRAWN.** The arm *can* get its palm to the block's centre. I reasoned from a "first contact at z = 0.0350" figure without checking the contact-height sweep that was **already committed** in `evobot_t08_saturation_diagnosis_20261112/HEIGHT_SWEEP_RESULT.md`: 0.0175 → **151.14 mm**, 0.0200 → 69.92 mm, 0.0300 → 0.59 mm (no contact). **Fourth rediscovery of the session.** | `evobot_lead_t08_centre_height_20261112/` |
| **T08 at the correct contact height** | **SIMULATION TESTED, n = 1, dev seed2000, PRE-REGISTERED.** `contact_height_m` 0.0200 → **0.0175**, `overdrive_m` → 0.005. Result: displacement **0.10576 m**, cosine **0.99914**, Δz **−0.0001 m**, **contact never lost**, block measured `[0.220,0.000] → [0.114,−0.004]` | `evidence/push.json` |
| **Graded against the task's own criterion** | **ALL FOUR SUB-CLAUSES PASS.** displacement 0.1058 ∈ [0.030, 0.150] ✓; \|Δz\| 0.0001 ≤ 0.020 ✓; cosine 0.9991 ≥ 0.90 ✓; **zone distance 0.0072 ≤ 0.060 ✓** — the block stopped **7.2 mm from the zone centre** | same |
| The skill's verdict on that same run | **FAILED, ec=36 ERR_DISPLACEMENT_OVERSHOOT** — it moved 15.8 mm beyond the **requested** 0.09 m against a 5 mm tolerance, while the task accepts a **120 mm band**. Both contracts are honest; they measure different things | same |
| Where T08's recorded 0/6 came from | **`contact_height_m = 0.0200`** — `evobot_t08_evidence_loop_20261112/freeze_policy.py:75`, confirmed in that README §4. **A height later shown to lose contact.** The 0/6 was truly measured; it was measured at the wrong height | same |
| My own prediction for this run | **FALSIFIED at its bound.** I predicted displacement 0.085–0.105 m; actual **0.10576 m**, outside by **0.8 mm**. Cause: I converted overdrive to travel assuming 1.00× when it is ≈1.11× because the block slides on after the push. Not claimed as a confirmation | same |
| Evidence level | **Simulation Tested (n=1, dev).** **NOT generalisation.** Dev seed2000 was used for tuning; unseen seeds 3000–3002 were already spent and are not reusable after tuning. A generalisation measurement requires **fresh** instances generated after this configuration is fixed | — |
| What is NOT claimed | T08 is **not** solved (one run, one seed, one configuration); the skill is **not** broken (it correctly refused a push beyond what was asked); the recorded 0/6 was **not** false | — |
| **T08 skill-level** | **unchanged at 0/6** by the mission's skill-level definition (the skill self-certified nothing). What changed is `execution_succeeded` against the task criterion: **1/1 on dev**, versus 1/7 previously observed on unseen at the wrong height | — |

---

## ADDENDUM — goal round 9 (2026-11-12): the round-8 result does NOT generalise. 2 of 6.

| Fact | State | Evidence |
| --- | --- | --- |
| Round 8's "working configuration" | **OVER-READ — CORRECTED.** Six instances frozen by sha256 **before any run** (`t08_fresh_zone_20261112/freeze_manifest.json`), pre-registered prediction **6 of 6**, measured **2 of 6**. The prediction is **FALSIFIED** | `evobot_lead_t08_fresh_unseen_20261112/` |
| **The push is not repeatable** | **CONFIRMED.** Identical commands (`contact_height_m = 0.0175`, `overdrive_m = 0.005`, `distance_m = 0.09`, same direction) produced displacements **0.000, 0.013, 0.036, 0.041, 0.082, 0.102 m** — a spread of **0 to 102 mm from one command** | same |
| What round 8 actually was | **one draw from a wide distribution**, not a configuration that works. The correct reading of 0.1058 m is a lucky sample, not evidence of capability | same |
| What the contact-height change bought | **a higher ceiling, not reliability.** Max observed rose 69.9 mm (at 0.0200) → **101.8 mm** (at 0.0175); contact was still lost in **4 of 6** runs. **Necessary and not sufficient** | same |
| T08's remaining blocker | **CONTACT REPEATABILITY — a control problem, not geometry.** Not reach (rounds 6–7 were wrong), not contact height alone (round 8 was over-read) | same |
| Task-clause satisfaction at the corrected height | **2 of 6 fresh unseen = 33 %.** Previously 0 of the recorded runs at 0.0200 | same |
| `unmoved: target_box_b` | **UNMEASURED** in this experiment — the push action measures only the pushed object. A pass here is a **push-clause pass**, not a whole-task pass | same |
| Failure attribution | 4 runs **Control** (contact lost partway, measured). `seed5002` `ec=30 ERR_MOTION_FAILED` with 0 mm recorded **UNKNOWN** — one sample cannot separate control, transient and harness causes | same |
| T08 skill-level | **0/6, unchanged** — the skill certified nothing on any of the six | same |
| **Generalisation** | **NOT CLAIMED.** The instances are spent; re-tuning on them and re-running would be the manufactured-success pattern the freeze manifest exists to prevent | — |
| A first instance set (seeds 4000–4005) | **GENERATED AND DISCARDED UNRUN.** `/home/ros/flexcell-p14/scripts/sim_profile.py` always spawns `target_box_a` at **(0.22, 0.0)** — it cannot place an arbitrary box pose — so those instances would have graded against a zone while the simulator put the block elsewhere. Replaced by a set that varies the **zone** only, which narrows the claim to **generalisation over zone placement** | same |

---

## ADDENDUM — goal round 10 (2026-11-12): the variance mechanism is in the logs, and overdrive helps but not enough

| Fact | State | Evidence |
| --- | --- | --- |
| **Why T08's push is not repeatable** | **FOUND IN THE LOGS, not inferred.** `move_to_pose.jsonl` for the round-9 runs: commanded `z = 0.0175` but **reached z 0.021–0.022** (a consistent **+0.004 m**), **`orientation_enforced: False`**, **orientation error 0.44–1.02 rad (25–58°)**. The tool attitude is whatever IK returns and varies run to run; the achieved contact height lands on the committed sweep's **cliff** (0.0200 → 70 mm, 0.0225 → 6 mm) | `evobot_lead_t08_overdrive_20261112/` |
| **Reconciliation of round 8 vs round 9** | **Arm travel = `requested + overdrive`.** The sweep's 151 mm came from **overdrive 0.05** (travel 0.14 m); my six runs used **0.005** (travel 0.095 m). **They were never the same experiment** — the 151 mm was not evidence that 0.0175 works better | same |
| Pre-registered overdrive test | **PREDICTION FALSIFIED.** Predicted **≥5 of 6** at `overdrive_m = 0.030`; measured **3 of 6** (round 9 baseline 2 of 6). Reported as a miss; instances not re-tuned | same |
| **`agent_claimed_success` for T08** | **1 — the first of this session.** `seed5001`: displacement 0.0934 m against a 0.090 request (3.4 mm error, inside the skill's 5 mm tolerance), **`outcome = 0`, `error_code = 0`** | same |
| **False Success** | **0.** The single success was independently confirmed inside **both** the displacement band and the zone | same |
| **New failure mode** | **`seed5000` was pushed BACKWARDS**: displacement 0.0056 m with **cosine −0.765**. Overdrive made the arm ride over the block and flick it the wrong way. Neither the skill's taxonomy nor mine had this in view | same |
| `seed5002` | **failed identically twice** (`ec=30`, zero displacement) at both overdrive settings — raised above coincidence from `UNKNOWN`-on-one-sample to **reproducible**, but the **cause remains UNKNOWN** (control vs harness vs world generation not distinguished; not investigated) | same |
| The pattern across rounds 9–10 | **Every request-field lever moves the pass count by about one run in six** (2/6 → 3/6). That is the signature of a **marginal contact** whose outcome is set by an uncontrolled variable (tool attitude), not of a parameter that needs tuning | — |
| T08 skill-level on the **unseen** set | **0/6, UNCHANGED.** The 5000–5005 set was **spent in round 9**, so round 10 is a **configuration result on spent data**, not generalisation | — |
| `unmoved: target_box_b` | **still UNMEASURED** — the push action measures only the pushed object | — |

---

## ADDENDUM — goal round 11 (2026-11-12): round 10's explanation is withdrawn; the real cause is operation at the reach limit

| Fact | State | Evidence |
| --- | --- | --- |
| Round 10's "uncontrolled variable is the tool attitude" | **REFUTED — WITHDRAWN.** Comparing reached orientations across separate runs at byte-identical commanded poses: max difference **1.4–4.5°** (one 22° outlier at the pre-push standoff). The 0.44–1.02 rad `orientation_error_rad` is a **systematic offset against the requested identity**, not run-to-run scatter | `evobot_lead_t08_height_offset_20261112/` |
| What actually varies | **ACHIEVED end-effector height: 0.0198 – 0.0249** (~5 mm scatter) around a commanded 0.0175. The block starts at exactly `[0.22, 0.0, 0.0175]` in every usable run — **zero variance** — and attitude is repeatable, so height is the only remaining variable | same |
| Why that matters | The committed sweep is extremely sensitive there: **0.0215 → 151 mm, 0.0240 → 70 mm, 0.0265 → 6 mm**. The ~5 mm achieved-height scatter **straddles the cliff**. Quantitative mechanism, no free parameter | same |
| Pre-registered height-offset test | **FALSIFIED.** Predicted `contact_height_m = 0.010` would achieve 0.012–0.018 and ≥0.060 m displacement; measured **0 of 3, all `ec=30`, zero motion** | same |
| Why it failed — not a harness fault | `move_to_pose.jsonl`: **`outcome=POSE_NOT_REACHED`**, `ec=30`, **`ik_precheck.ok=True`, `'IK solution found'`**. IK finds a solution; the arm cannot execute it. **The reachable floor sits above the commanded height, so the cliff cannot be escaped with a request field** | same |
| `seed5002` re-attributed | **UNKNOWN → Control / kinematics.** Its `move_to_pose` log in **both** earlier batches shows the **ordinary approach pose `[0.2575, 0, 0.0175]`** failing with `ec=20`, IK ok, `reached_pose=None` — reproducibly twice, in a world that is byte-identical every run. Named by its own log, not by preference | same |
| **Three request fields, three falsifications** | contact height 0.0200→0.0175 (**1/1 dev, then 2/6 fresh**); overdrive 0.005→0.030 (**3/6** vs predicted ≥5/6); contact height 0.0175→0.0100 (**0/3**, unreachable). **The request-field avenue is closed by measurement, not assumption** | — |
| What remains, and it needs approval | (1) **Control layer** — command an explicit tool orientation and a pose inside the reachable envelope, instead of `orientation_enforced: False` with a pose on the boundary (`contracts/push.py` / `push_server.py`, **both frozen**). (2) **Tool geometry** — a side-mounted probe, a robot-description change | — |
| False Success across **every** T08 run this session | **0** | all runs |
| T08 skill-level on unseen | **0/6, unchanged.** `agent_claimed_success` = 1 (round 10 `seed5001`) | — |

---

## ADDENDUM — goal round 12 (2026-11-12): P3's seven-field records, audited and independently reviewed

| Fact | State | Evidence |
| --- | --- | --- |
| P3's "seven-field experience records **with independent review**" | **NOW DELIVERED AS A REVIEW, AND IT FAILS.** 4 records exist, hash chain intact; no review existed before this round. My audit + `gate-auditor`'s independent review give: **0 ACCEPT / 1 ACCEPT-WITH-CORRECTION / 3 REJECT** | `evobot_lead_experience_review_20261112/` (README + REVIEW.md) |
| **The systematic cause** | **The archive holds the POST-FIX run while the evidence describes the PRE-FIX failure.** The defect was fixed before the directory was archived, so **the cited source cannot contain the evidence by construction**. A reader doing what `source_run` invites finds a **PASSING run in 3 of 4 cases** | same |
| Verified independently by me, not accepted on report | R1's cited run **passed** — `evobot_t01_baseline_a_20261111/task.out` = `{ok:true, outcome:0, error_code:0}` while the record says `outcome: failed`. R4's `task_id` `T03-heldout-seed9000` occurs **0 times** in its cited source | same |
| `validated: true` | **DOES NOT MEAN REVIEWED.** `store.make_record` sets `False` (`store.py:56`); **`seed_from_evidence.py:31` overwrites it to `True`** before append. It records "the seeder ran", in a field name every reader will read as "a second party checked" | same |
| The scope guard | **DOES NOT GUARD WHAT IT CLAIMS.** All **8/8** lesson/evidence blocks pass `_check_scope`, yet **3 of 4 lessons are not planner-level**. It is a keyword denylist against smuggling *the answer* — evadable by one synonym (R4 says "landing spots", not "placement"). **A denylist is not a boundary** | same |
| Actionability | **1 of 4** lessons could move a plan (2 HARNESS, 1 DOWNSTREAM_CODE). The one actionable lesson addresses **`error_code 64`, which appears in NO machine-readable archive file** — only in 3 README narratives | `evolution/transfer/audit_actionability.py` + my audit |
| Exact cited evidence found in a machine-readable file | **0 of 4** (all README prose) | my audit |
| **A recorded disagreement** | The review states R3's evidence is real ("the only one whose evidence is in actual run logs"). **Not confirmed for the cited string:** "Failed to find a free participant index for domain **213**" appears only in that batch's `README.md:19`; `runs/s1004-a1/stack.log` shows the same **class** with **domain 233**. Its broader point has a basis; its specific claim does not hold on the record as written. **Both readings recorded rather than adopting the more flattering one** | same |
| **P4 becomes answerable with a mechanism** | **EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED** — and the reason is not merely "not measured": **1 of 4 lessons could act on a plan, that lesson addresses a failure absent from every machine-readable archive file, and 0 of 4 records are re-derivable from their own cited source.** A cross-task reuse arm has nothing to reuse. **P4 itself is still not complete** — D's definition remains unformalised (`§7.5` says it must not stay undefined while also calling itself a proposal pending North Star, which is `BLOCKED_MISSION_TEXT_MISSING`) | — |
| The review's ranked fixes | **RECORDED, NONE APPLIED.** Highest value ≈10 lines: **make the seeder assert the evidence values actually appear under `source_run`** — that alone would have rejected 3 of 4. *"The difference between a claim and a check."* | REVIEW.md |
| What the channel does have | The hash chain, append-only design and scope guard **all exist and work**; `audit_actionability.py` had already reached the same 1/4 conclusion and is simply **not wired into the write path**. These four records are evidence the channel can be **populated** and that its integrity machinery **runs** — not that it works | same |

---

## ADDENDUM — goal round 13 (2026-11-12): the seeder now checks evidence, and rejects all four records

| Fact | State | Evidence |
| --- | --- | --- |
| **The provenance defect** | **FIXED in the write path.** `seed_from_evidence.py:26` was the only check (`if not source.exists()`); it **never opened the directory**, and set `validated = True` itself at line 31. New `verify_provenance.py` requires **every evidence string** to appear in a **machine-readable** file under `source_run` (prose excluded by suffix), and refuses `HARNESS`/`DOWNSTREAM_CODE`/`UNCLEAR` lessons at **write** time | `evobot_lead_provenance_fix_20261112/` |
| Demonstration against the four real seeds | **0 accepted, 4 rejected.** The round-12 review predicted 3 of 4; the mechanical check tests the **exact cited string** and therefore rejects R3 too (record says domain **213**, `runs/s1004-a1/stack.log` says domain **233**). **The round-12 disagreement is now settled by a check rather than an argument, against the more generous reading** | same |
| Tests | **7/7 pass**, including the three cases where a naive check passes: evidence only in a README (the actual historical defect), a missing source, and evidence with no verifiable string | `evolution/experience/test_verify_provenance.py` |
| Schema, changed conservatively | `validated` is **no longer set by the seeder**; new fields `provenance_verified`, `evidence_files`, `reviewed_by`, `review_verdict`, `review_ref` record what was actually checked | same |
| `records.jsonl` | **NOT rewritten, not reseeded.** The four records keep `validated: true` because that is now the historical fact that the old seeder ran — editing them would destroy evidence of the defect | `git diff` shows 0 changes |
| **What this does NOT fix** | **The store cannot currently be reseeded from its own seed file**, because the seeds cite evidence the archives do not contain. Three of the review's five ranked fixes remain open: `source_run` pointing at the **run** not the batch, **archiving the failing run** when a defect is fixed, and reviewer-owned verdicts | same |
| Net effect on P3 | **The channel is HONEST, not FUNCTIONAL.** An empty store that refuses bad records is a better foundation than a populated one that accepts them — but it is not experience reuse | — |

---

## ADDENDUM — goal round 14 (2026-11-12): the fixed seeder ACCEPTS — two provenance-verified records

| Fact | State | Evidence |
| --- | --- | --- |
| Can the fixed pipeline accept a **genuine** record? | **YES — 2 accepted, 0 rejected.** Without this the channel would be dead rather than strict | `evobot_lead_verified_records_20261112/` |
| Where genuine machine-readable planner evidence exists | **Exactly two distinct failures** in the whole archive, both under `evobot_recover_n6_20261111/runs/HO-90899d657e68/sim/skills/composites/`: **`ec=61` n=3** `'state drift or occupied destination before target_box_b-1'` and **`ec=60` n=2** `'declared destination occupied at target_box_b-1'` | same |
| The failure legacy record **R4** claimed | **REAL.** R4 cited the wrong source and the wrong context, but the occupied-destination failure genuinely happened and now has a machine-readable citation. *A wrong record about a real event* | same |
| Records added | `T05-recover-occupied-stage` and `T05-recover-declared-occupied`, both `provenance_verified: True`, `validated: False`, evidence files present and re-checked after writing | `records.jsonl` now 6 records, chain intact |
| A filter I broke, and fixed | `audit_actionability.py` filtered on `validated`, which after round 13 means **"the OLD seeder ran"** — so it reported on the 4 **least** trustworthy records and ignored the 2 verified ones. Now partitions by `provenance_verified` and reports **both cohorts** | `evolution/transfer/audit_actionability.py` |
| **The result that matters for P4** | **verified cohort: 2/2 PLANNER_ACTIONABLE**; unverified cohort: **1/4**; combined **3/6**. **Every verified record is planner-actionable, most unverified ones are not — so the defect was in the SEEDING, not the concept** | same |
| P4 statement updated | Round 12: "a D arm has nothing to reuse." Now: **two actionable lessons about a failure that genuinely occurs (5 logged instances)**. **P4 is still not complete and not closer to passing** — those lessons may never arise on the frozen unseen set, and D remains undefined behind `BLOCKED_MISSION_TEXT_MISSING` | — |
| Still wrong, stated plainly | (1) `validated: True` on the four legacy records still does not mean reviewed, so **two conventions coexist under a misleading name**; (2) **no independent reviewer has signed either new record** — `reviewed_by`/`review_verdict`/`review_ref` are `None`, and **provenance verification is not review**; (3) `source_run` still names a run **directory**, not a single artifact | same |
| Seeder capability added | `--append` mode, justified because append is inherently safe (dedup by `record_sha256`, never rewrites, never deletes) and without it the store could never gain a record after the old seeder's first run | — |

---

## ADDENDUM — goal round 16 (2026-11-12): provenance now verifies NUMBERS, and still cannot catch a false lesson

| Fact | State | Evidence |
| --- | --- | --- |
| The round-15 hole | **CLOSED.** `evidence_strings()` skipped every number, so `error_code 99` passed in place of 60 — demonstrated by the reviewer. Numeric and boolean facts are now checked **structurally**: they must match a **typed field value in a parsed JSON object** | `evobot_lead_numeric_provenance_20261112/` |
| Why not a substring test | `60` occurs in timestamps, coordinates and ports, so a text search proves nothing. `_matches` also refuses `True == 1` | same |
| Tests | **11/11**, two of them built from the reviewer's own corruptions: `error_code 99` → REJECT, and `error_code 0` present only as a substring of `60` → REJECT | `evolution/experience/test_verify_provenance.py` |
| Against the six real records | the 2 genuine ones still **PASS with their error codes verified**; the 4 legacy ones still **FAIL** | same |
| **The reviewer's fix 4 remains OPEN and it is the one that matters** | provenance proves **the failure happened and its code**; it does **not** prove the lesson follows. **Both rejected records would still pass every check in the verifier — real evidence, real error codes, false lessons.** What caught them was a human-readable review, **not a check**, and no check yet written would have caught them | same |
| A test had to change | *"evidence is all numbers -> REJECT"* asserted the **old, wrong** behaviour. Numbers are verifiable now, so its premise was obsolete, not its expectation | same |
| Did NOT add a corrected record | The reviewer supplied the true finding (a control/tooling fact about ±28 mm spread vs 50 mm clearance). **Not added** — authoring another lesson before the check exists that catches false ones is exactly how round 14 produced two wrong records. Store stays at 6 records, 2 provenance-verified, **0 review-grade**, retrieval 0 lessons | — |

---

## ADDENDUM — goal round 17 (2026-11-12): P2's request-field avenue is closed by a MEASURED capability limit

| Fact | State | Evidence |
| --- | --- | --- |
| **Arm pose repeatability at contact height** | **sd 3.44 mm, total spread 20.37 mm** over **n=197** successful archived moves (commanded z ≤ 0.06). Achieved z: mean 0.0237, range **0.0165–0.0369** | `evobot_lead_pose_repeatability_20261112/` — **zero Gazebo runs** |
| **The cliff it must land on** | **2.5 mm wide** (69.92 mm → 6.32 mm displacement between achieved 0.02125 and 0.02125+). **The scatter is ~8× the feature** | same |
| Where a single fixed command lands | across the **entire** sweep: 151 mm 2.0%, 69.92 mm 14.7%, 6.32 mm 43.1%, 3.55 mm 25.9%, 0.59 mm 14.2% | same |
| Systematic offset vs height | drifts **−1.92 mm to +3.75 mm**; scatter is **~3.5 mm at every height**. A height-dependent calibration would remove the drift and leave the scatter | same |
| `position_error_m` over 3,426 successes | **mean 6.53 mm, median 6.76, p95 9.16, max 19.43 mm** — against `position_tolerance_m` accepting 20 mm, the controller routinely runs near its own tolerance | same |
| **Conclusion** | **No request-field value can fix T08.** Not because the right value is unknown, but because for any fixed command the arm lands somewhere in a 20 mm distribution several times wider than the behavioural feature. Choosing another command relocates the distribution; it does not narrow it | same |
| What this retires | Round 10's *"the uncontrolled variable is tool attitude"* — **wrong**, attitude is repeatable, **position is not**. Round 11's 5 mm scatter — **understated by 4×** on the smaller sample | same |
| What would actually work (all need approval) | (1) repeatability well under 2.5 mm; (2) remove the cliff; (3) **close the loop** — measure the achieved pose and act on it, in `contracts/push.py`/`push_server.py`, **both frozen** | — |
| Thresholds | **none lowered, none proposed.** Sweep, evaluator and criteria unchanged. The claim is narrower than "too hard": the skill must resolve a 2.5 mm feature with a 20 mm actuator distribution | same |

---

## ADDENDUM — goal round 18 (2026-11-12): P1's *recover* measured for the first time — 18/24 = 75%

| Fact | State | Evidence |
| --- | --- | --- |
| **P1 recover (bounded single retry)** | **18 / 24 = 75%.** Of 24 episodes whose first attempt failed, **18 completed on the one permitted retry**. The 6 that failed got no third attempt (`budget: 1`, by design) | `evobot_lead_recovery_measured_20261112/` — **zero Gazebo runs** |
| P1 diagnose | **fires correctly**: 26 failure classifications recorded (grasp 18, UNKNOWN 6, planning 2) | same |
| Runtime recovery decisions | **110 records, all `no_recovery`** — 104 *"first attempt succeeded"*, 6 *"goal already satisfied by measurement"*. Those runs never needed recovery | same |
| Why 75% is a capability, not success manufacturing | decided from **execution** evidence (`task.out` RESULT), **never** the graded verdict; evaluator consulted only after all attempts; `original_failure_preserved: True` on all 26; a guard refuses to retry a **false** failure (*"worse, made 'arm R' look exercised when it was not"*); retries bounded to 1 | `runtime/recovery/recovery_driver.py:2-7,57-63` |
| An error I made and caught | I first tested for retries by looking for **sibling directories** (`-a2`), found none, and nearly wrote *"24 retry plans built, 0 executed"*. The retry actually runs **in the same directory**, writing `task_retry.out`, invoked from `evobot_unified_runner_20261111/run_batch.sh:113`. **My heuristic was the bug, not the code** | same |
| A concern I raised and then resolved | I suspected the baselines might count the original failure and so **understate** the project's capability. **Checked: they do not.** `summarize_recovery.py:63-72` has a first-class **`RECOVERED`** category alongside FIRST_TRY / STILL_FAIL | `experiments/baselines/summarize_recovery.py` |
| **What this does NOT change** | **It is not T08** (pick/carry/place, not push — T08 stays **0/6**, round 17's ±3.44 mm vs 2.5 mm cliff untouched). **It is not Generalization Tested** — these are held-out instances used while recovery was being developed, so no transfer claim to unseen seeds | — |

---

## ADDENDUM — goal round 19 (2026-11-12): the planned n=22 test is under-powered; the real requirement is n=53/arm

| Fact | State | Evidence |
| --- | --- | --- |
| The prior audit's `n ≈ 22 per arm` | **CIRCULAR.** It was sized to detect **80% vs 40%**, and those numbers come from the **same n=5 sample** (4/5 vs 2/5) the study exists to replace. The effect size used to size the experiment was estimated from the experiment being sized | `evobot_lead_power_analysis_20261112/` |
| Independent per-draw estimate | Round 17's 197 contact-height samples: only the **69.92 mm** band passes the frozen [30, 150] mm clause → **14.7% per draw**. With `push_recover`'s 3 attempts: **38.0%** | same |
| Real effect size and requirement | **23 points, not 40** → **n = 53 per arm = 106 Gazebo runs** (not 44) | same |
| Power of the planned test | **0.44** at n=22. It would most likely return a null that is **indistinguishable between "no effect" and "not enough data"** — uninterpretable, for ~44 runs | same |
| **Decision handed back** | **Do not run the 22-per-arm test.** Either fund **106 runs** (~5+ h of continuous Gazebo against a one-instance-at-a-time lock) or accept the recovery effect stays unestablished. **A resource decision, not one to absorb into a round** | same |
| What this does NOT say | **Not** that recovery fails — the distributional finding stands independently of power: the recovery floor moved **2.6 mm → 74.0 mm**. **Not** that 14.7% is exact (pooled across batches, not the single instance used) | same |
| Synthesis | single draw lands across 20.4 mm with ~15% passing (r17) **+** recovery retries a short push and lifts the floor (prior audit) **→ a real but modest ~23-point effect**. That is why 4/5 vs 2/5 looked dramatic and is not | same |
| Environment pre-flight | all 5 setup files present, no stray sim process, task spec present, lock free — **the run was feasible and I chose not to spend it** | `_r19_pre.sh` output |

---

## ADDENDUM — goal round 20 (2026-11-12): the recovery experiment already contains BOTH arms, paired — and it shows one trial changed

| Fact | State | Evidence |
| --- | --- | --- |
| The published comparison | **WRONG COMPARISON, not merely underpowered.** 2/5 vs 4/5 crosses **two different experiments**. The recovery run **already contains a single-shot arm**: a trial with `attempts == 1` IS single-shot (first attempt = only attempt), and `attempts > 1` failed its first attempt **by construction** | `evobot_lead_paired_audit_20261112/` |
| **The paired result** | first-attempt **3/5** → final **4/5**. **1 discordant pair improved, 0 regressed. McNemar exact p = 1.0.** *Within its own experiment, recovery changed exactly one trial out of five* | same |
| Consequence for cost | pairing is the stronger design **and halves the runs** — round 19's n=53/arm estimate is **pessimistic in cost**; a paired design needs far fewer than 106 runs, though far more than 5 | same |
| **The 2/5 baseline does not reproduce** | `repeats.tsv` graded on its **recorded** columns (displacement, cosine) gives **3/5**, not 2/5 — trials 1, 2, 3 all pass on both clauses. **NOT declared wrong**: the frozen clause has four sub-clauses and the other two (`|Δz| ≤ 0.020`, zone radius) are **absent from the artifact**. The finding is that **the baseline in the headline comparison cannot be verified from the archive that is supposed to support it** | same |
| What stands | recovery lifts the distribution floor **2.6 mm → 74.0 mm** (prior audit) — real, and independent of pass rates. A single draw lands across **20.4 mm, ~15% passing** (round 17, n=197) | — |
| **Net honest statement** | **the recovery mechanism is real and visible in the distribution; the pass-rate improvement is one trial in five.** That is what should be written down, not 2/5 → 4/5 | same |

---

## ADDENDUM — goal rounds 34–38 (2026-11-12): the round-17 T08 conclusion is WITHDRAWN

> **READ THIS BEFORE CITING ANY T08 NUMBER IN THIS FILE.** The round-17 entry above states that P2's
> request-field avenue was closed by a measured capability limit (±3.44 mm repeatability against a 2.5 mm
> cliff). **That conclusion is withdrawn.** The arm can perform T08. The measurement was of a harness that
> withheld evidence the frozen evaluator requires.

| Fact | State | Evidence |
| --- | --- | --- |
| The decisive code | `evaluate.py:227` reads `traj` from the state file; `:221` **fails closed** without one. `:253` `terminal_passed` is the clause conjunction. `:331-332` `passed` **additionally** requires a verified evidence bundle | pinned evaluator v0.5.0 |
| **T08 terminal clause, independently re-graded** | **4/5** with ≤3-attempt recovery. The frozen evaluator re-run over the pilot's stored `traj_t1..t5.json` gives False,True,True,True,True. Trial 1 is a genuine failure — cosine **−0.99975**, box went **backwards**, outside zone | `VERIFIED_REGRADE.md` |
| **T08 full pass** | **Achievable and achieved.** `t08_contact_calibration/runs/H0200/t1` and `t08_evidence_loop/evidence/S/t3` both show term=True passed=True; 9 T08 verdict files contain a true `passed`. **The 9 is not a result** — some may be the same trial re-graded | `T08_FULL_PASS_EXISTS.md` |
| **My own paired run (0/26)** | **VOID, WITHDRAWN.** Its state files carried no `trajectory` key, so the clause failed closed **for every trial regardless of robot behaviour**. A test whose every observation is forced to one value cannot detect an effect | `RESOLVED.md` |
| Round 20's paired **3/5 → 4/5** | **CONFIRMED** by independent re-grade; its one discordant pair is trial 5 (first attempt failed, retry succeeded) | round 37 |
| **What was never the constraint** | displacement. Every failing trial failed the same conjunctive clause, and I modelled the wrong sub-clause for twenty rounds | rounds 27–38 |
| **P2's real blocker** | **evidence plumbing, not robot capability.** The harnesses measuring T08 have not consistently supplied the evidence the frozen evaluator demands — mine included | same |
| What is still NOT established | **T08 at scale on unseen instances** — no clean run at n. **Generalization Tested: NO.** | — |

**The error, for the record:** for twenty rounds I reported that this arm could not perform T08, from a graded
number produced by a harness that withheld the required evidence. The `reason` string naming exactly what was
missing was printed in **every** verdict: *no trajectory for this object, end state alone cannot prove it was
pushed rather than carried*. **I read that as a verdict instead of as an instruction about my harness.**

---

## ADDENDUM — goal rounds 44–47 (2026-11-12): T08 reaches **Generalization Tested** (n=3, single-shot confirmed)

> **This supersedes the "Generalization Tested: NOT ESTABLISHED" line in the rounds 34–38 addendum above.**

| Fact | State | Evidence |
| --- | --- | --- |
| **T08 full pass on an UNSEEN instance, in ONE push** | **CONFIRMED.** `TRIAL_RECORD` for `U_shot/seed3000/t1` records `attempts: 1`, `clause_ok: true`, `evidence_status: COMPLETE`, `failed_clauses: []`, `failed_gates: []`, displacement **147.14 mm** (inside [30,150]), `direction_cos` **0.9963**, `dist_to_zone` **48.28 mm** (≤60) | `evobot_t08_instance_pose_20261112/runs/U_shot/seed3000/t1/logs/evidence.log` |
| **All nine anti-fake gates satisfied** | `trajectory` **6680 samples**; `no_lift` max **0.000788 m** vs 0.02; `no_attachment` **0 events**; `pusher_contact` **1176/1182** motion windows with gripper collision links named; gripper aperture travel **0.000391 rad** vs 0.002; `table_support` **0** off-table; `protected_unmoved` **0.0 m**; `no_teleport` **0.000561 m** vs 0.03 | `.../t1/verdict.json` |
| Why that matters | **These are precisely the gates that make T08 unfakeable by pick-carry-place**, which the Master Goal demanded. `no_lift` + `no_attachment` + aperture stability prove the box was **not grasped**; `pusher_contact` proves the gripper links **did** contact it | same |
| **False Success** | **0.** `false_success: false`, `agent_claimed_success: false`. The skill even flagged its **own** push with `ERR_DISPLACEMENT_OVERSHOOT` (ec 36) while the graded outcome was inside the bound — **conservative about itself** | `TRIAL_RECORD` |
| Further instances | `U_shot/seed3001`, `U_shot/seed3002`, and closed-loop `U/seed3000`, `U/seed3002` all carry `passed: true` by the same gate pattern | verdict scan |
| **Evidence level** | **Generalization Tested for T08** — with the immediate caveat that **n = 3 distinct unseen instances is thin**; the evidence **quality** is high, the **breadth** is not a generalization study | — |
| What this supersedes | Round 17's *"this configuration cannot do this task"* — **FALSE**, and it stood for twenty rounds. Round 33–40's 0/26 — **VOID** (no `trajectory` key, clause failed closed) | — |
| Still not claimed | P3 unchanged (**0/6** records review-grade); P4 **`EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED`**; **L4 Develop not crossed** | — |

**How the error was made, for the record:** for twenty rounds a graded number said *cannot* while the artifacts
said *done*. I believed the number. The verdict printed the reason on every single failure — *no trajectory for
this object* — and I read it as a verdict instead of as a diagnosis of my own harness.

---

## CORRECTION — goal round 50 (2026-11-12): T08 Generalization is **n=2**, not 3

> **This corrects the addendum immediately above.** That addendum said n=3 thin. The correct width is **two**.

Checking **every** U / U_shot trial record rather than the verdict scan (whose `passed: true` is not the same as
valid evidence):

| trial | attempts | clause_ok | `evidence_status` | valid? |
| --- | --- | --- | --- | --- |
| `U_shot/seed3000` | 1 | True | **COMPLETE** | **YES** |
| `U_shot/seed3002` | 1 | True | **COMPLETE** | **YES** |
| `U_shot/seed3001` | 1 | True | `COMPLETE_EVIDENCE_CONTRADICTS_PUSH` | **NO** |
| `U/seed3000` | 1 | True | `COMPLETE_EVIDENCE_CONTRADICTS_PUSH` | **NO** |
| `U/seed3002` | 3 | True | `INCOMPLETE_OR_INVALID_EVIDENCE` | **NO** |
| `U/seed3001` | 1 | False | `INCOMPLETE_OR_INVALID_EVIDENCE` | no |

**`COMPLETE_EVIDENCE_CONTRADICTS_PUSH` is not a pass.** It reports that the evidence conflicts with the push
claim. Counting it because a separate flag said `passed: true` is the error this session keeps repeating —
**trusting a summary flag over the artifact that qualifies it.**

| fact | corrected state |
| --- | --- |
| valid unseen full passes | **2: `U_shot/seed3000`, `U_shot/seed3002`** — both single-attempt, `evidence_status: COMPLETE`, all nine anti-fake gates, zero false success |
| T08 evidence level | **Generalization Tested at n = 2** — the mechanism is demonstrated, the evidence quality is high, **the breadth is two instances** |
| closed-loop `U` runs | **neither valid** |
| what may NOT be quoted | "three unseen instances", and any Generalization claim wider than **two** |

**Sequence of my own widths for this claim: 9 → 5 → 3 → 2.** Each reduction came from reading one more
qualifying artifact. The honest number is **two**, and two is not a generalization study.

---

## ADDENDUM — goal round 51–52 (2026-11-12): T08 is **Simulation Tested**, NOT Generalization Tested

> **Independent review by `gate-auditor` overturns the label in the two addenda above.** The count n=2 survives;
> **the word "Generalization Tested" does not.** `evobot_lead_t08_verify_20261112/REVIEW.md`.

### The wording that is now correct

> **"Simulation Tested — T08 push, 2 clean held-out instances (n=2), zero false success."**

### Why the label fails (three reasons, all independent)

| reason | detail |
| --- | --- |
| **The denominator was chosen after the results** | six runs over three instances on two arms. **Both arms ran all three seeds.** The claim kept the arm that passed and dropped the arm that failed — **arm selection, unless `U_shot` was declared primary before the batch. No such pre-registration exists**: `run_batch_v2.sh` takes arm as a parameter and defines no primary. Honest denominator: **6 runs on 3 instances, 2 passed** |
| **The capability is stochastic on the SAME instance** | `U/seed3000` and `U_shot/seed3000` are the **same task** (`task_sha256` identical `ede25524…`), same `contact_height 0.02`, same `attempts=1`, **run 2 minutes apart: 121.7 mm vs 147.1 mm with opposite verdicts.** At that variance **2/2 is not separable from a coin landing heads twice** |
| **Two instances from one family** | both passes are geometries ~30 mm apart inside a 30–150 mm band. That is not a generalization measurement |

### What was CONFIRMED, by re-execution rather than by reading a flag

| item | status |
| --- | --- |
| `U` genuinely means **unseen** | **CONFIRMED from the definition**, not the directory name: `generate_t08.py` lines 11–16, 89, 107 — `HELD = 3000-3002`, written to `t08_unseen/`, commented *"must NOT be run until the skill implementation is frozen"* |
| the nine gates | **CONFIRMED.** `evidence_status` is computed by `verify.py:474-477` from the gate list, not self-reported. Reviewer re-ran `verify.py` v1.0.0 on the archived bundles: **6 of 6 verdicts reproduce EXACTLY**, both COMPLETE at 9/9. Trajectories **6680** and **6500** samples; `no_lift` 0.788 mm and 0.02 mm; protected excursion **0.0**; `no_attachment` **0 events** |
| my exclusion of the two `COMPLETE_EVIDENCE_CONTRADICTS_PUSH` runs | **CORRECT as a pass criterion** — `verify.py:478-483` makes it a *positive claim of failure*, not absence of evidence |
| first valid instantiation of the unseen poses | **this batch is the first**; round-1 runs never instantiated the declared poses, so they measured nothing about those instances. **Do not write "never run"** |
| gripper bound was not tuned on unseen | `calib_G1/G3` both run `t08_dev/seed2000` — **point in the claim's favour** |

### A finding that is bigger than my claim: the gripper bound cannot tell push from grasp

**Both excluded runs pushed the box correctly.** `U_shot/seed3001`: push clause **ok=TRUE**, disp **144.0 mm**, cos 0.9906, vertical **0.00000**, in zone. `U/seed3000`: push clause **ok=TRUE**, disp **121.7 mm**, cos 0.9976, vertical **0.00000**, in zone. Both were rejected **on the `gripper` gate alone** — 0.0035 and 0.0030 against a 0.0020 bound.

The run's own record says why: *"on this arm the fingers are deflected by contact, so the bound is being crossed by a push."* Physics: vertical 0.00000, `max_lift` 0.39 mm against a 20 mm limit, `no_attachment` 0 events, 144 mm travelled **along the table**. **A box never lifted and never attached is not being carried — this is finger deflection during contact**, the F8 failure mode already recorded (bound sits **154× below** the pass value, bimodal, no samples between 1.287 and 3.057).

| consequence | |
| --- | --- |
| as a **pass criterion** | the exclusion **must stay** — I may not re-label runs to reach n=4 |
| as a **statement about the robot** | **the label is false; n=2 undercounts physical capability by at least 2** |
| scope | this affects **every T08 number this project has published, in both directions** — the gate that decides push-vs-grasp cannot tell them apart on this robot |

### seed3001 is burned — carry this caveat

The pose fix's own integration test targeted **seed3001** explicitly (*"integration on seed3001, worst case 70.7 mm"*). **It is the one that failed.** My n=2 excludes it because it failed, **not because it was excluded a priori** — the difference matters for how the denominator is read.

### My own four numbers, adjudicated

**9 → 5 → 3 → 2.** The review's verdict: *"2 is the FIRST of those that is defensible as a count — because I re-ran the verifier and it reproduces — and it is STILL not 'Generalization Tested'. **The narrowing was not the error. The label on top of the number was.**"*

---

## ADDENDUM — goal round 60 (2026-11-12): P4's root cause, and why the archive cannot supply the missing evidence

| Fact | State | Evidence |
| --- | --- | --- |
| **Why C has never shown an advantage** | **C's retrievable set is empty because the planner is never wrong in the archived record.** This replaces the earlier *symptom* explanation ("the channel contains no actionable lesson") with the root cause | `evobot_lead_p3_record2_20261112/README.md` |
| The audit | **four independent checks, all zero**: `failure_layer` — 0 of 64 runs planning-attributable; 41 plans vs 120 task specs — 0 wrong zone / missing leg / protected move / omitted object; **211 runs** vs requirements rebuilt from each run's **own** `verdict.json` — **0 genuine plan defects**; zone-identity sweep — **0 misrouted** | same |
| The record that would have been plausible and false | `plans/T05-train-seed1000` emits one move `b→zone_2`, which reads as a skipped relay. **It carries `"via":["zone_1"], "stages":2`.** Reading `via` correctly removes the only apparent planning error in the set | same |
| The only genuine planner-side failure | **one event, archived twice**: `T06-train-seed1001`, `agent_plan: null`, `raw_reply: ""` — **zero characters while 2625 tokens were billed**, 1 in 18 attempts. Correctly refused: the planner chose nothing, there is no plan to learn from, n=1 on an empty artifact | same |
| **The negative control, kept** | a **manufactured** planning lesson asserting the round-14 false finding printed `ACCEPT`. Retrieval gates on `failure_class ∈ {planning, state}` **plus** review ACCEPT, so it would have become **the first retrievable lesson in the store, and it would be false** — a false lesson entering plans | `NEGATIVE_CONTROL_false_planning_lesson.json` (do-not-append) |
| **The prerequisite, precisely** | **score plan correctness BEFORE execution**, so an actuator error cannot masquerade as a planning error. Until that measurement exists, **any planning-class record in this store is either mislabeled or invented** | same |
| **Why the archive cannot close it** | the archive holds **316 `plan.json` files but 0 `spec.json` for T13 and T06** — the hard families where the planner's choice can actually be wrong are barely represented, and every archived plan that was audited proved correct. **Producing a genuine planning error needs either new instances of T13/T05/T06 or paid model calls on the B planner** — a resource decision, not an analysis | this round |
| P4's statement, final for this session | **`EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED`** — with the cause at the root: *the planner is never wrong in the archived record, so there is nothing for C to learn, and the checker would admit a false planning lesson if one were manufactured to fill the gap* | — |

---

## ADDENDUM — goal round 61 (2026-11-12): the EVALUATOR is drifted from its pinned hash, and every T08 number depends on it

Integrity check at HEAD `b1457e8a`:

```
experience store : 7 records, chain intact
review ledger    : 3 entries -> REJECT, REJECT, ACCEPT
pinned baseline  : 9 files, DRIFT -> benchmark/evaluators/evaluate.py
```

| Fact | State |
| --- | --- |
| `benchmark/evaluators/evaluate.py` hash | **does not match `benchmark/capability_baseline.json`** |
| Was this known? | **YES, flagged in round 1 and never resolved** — it is not a new regression from this session's work |
| Why it was not resolved | **re-pinning a baseline is a human approval**, and reverting would discard whatever change produced v0.5.0 |
| Why it matters more now than in round 1 | **every T08 figure in this session — the 4/5, the 2 clean unseen instances, the `gripper` bound finding — was graded by this file.** The evaluator is the ruler, and the ruler is not the one that was pinned |
| What it does NOT mean | not that any number is wrong. The drift may be a legitimate update (v0.5.0 with the trajectory gates) whose pin was never refreshed. **Unverified either way** |
| The decision | **re-pin** (accept the current evaluator and update the baseline, which invalidates comparability with older results), or **revert** (restore the pinned evaluator, which discards v0.5.0), or **document the drift as accepted** and stop describing the baseline as intact |

**This is the single highest-leverage open item.** Every capability claim in this project is downstream of a file that
does not match its own stated pin, and the project has described that baseline as authoritative throughout.

---

## CORRECTION — goal round 62: the evaluator "drift" is a STALE PIN, not an unauthorised change

> **This downgrades the alarm in the addendum immediately above.** The drift is real; the framing was wrong.

`evaluate.py` has **eight committed revisions**, the most recent being:

```
4fd36cd6  fix(t08): the evidence verifier rejected every valid push because evaluate.py never passed limits
879d8d82  feat(t08): v0.5.0 -- the terminal verdict is no longer the whole verdict
332b844f  fix(p0): close two audit findings -- a pkill that would kill everything, and a push clause a carry could satisfy
0dc1245b  feat(evaluator): add the push clause, because a 60 mm push and no movement graded the same
```

`benchmark/capability_baseline.json` was last written at commit **`8e1ba83b`**, which **predates all of those.**

| claim | corrected state |
| --- | --- |
| evaluator modified outside review | **NO.** Every change is a committed, messaged revision |
| the ruler is unaccountable | **NO.** The ruler is accountable; **its pin was simply never refreshed** |
| risk to the session's T08 numbers | **LOW.** They were graded by the newest committed evaluator, which is the correct one to use |
| what is actually wrong | **the baseline still advertises 9 pinned hashes as if they described the current evaluator.** That is a bookkeeping defect, not a measurement defect |
| remedy | **re-pin `capability_baseline.json` to the current `evaluate.py`** and record which revisions the change covers. A low-risk update **only if the archived results are declared to be generated under v0.5.0+`4fd36cd6`** — otherwise older numbers lose comparability |

**I over-stated this in round 61.** "The ruler is not the one that was pinned" is true as bookkeeping and false in
implication: the pin is stale, the evaluator's history is fully documented, and the newest revision is the one that
fixed the very evidence-passing bug this session rediscovered from the other end.

**What remains genuinely worth flagging**: a capability baseline that lists hashes it no longer describes will keep
producing this alarm for every future reader, and the next person may act on it less carefully than this one just did.

---

## ADDENDUM — goal round 63 (2026-11-12): the Skill Curator's only measurement — adoption is ZERO, and why

The Master Goal names the Skill Curator a **permanent role measuring Development Skill effect with controlled
comparisons, never file counts**. Across 60+ rounds it had produced **nothing**. It was activated and measured.

| Fact | State | Evidence |
| --- | --- | --- |
| **Is there a controlled comparison?** | **NO — and none can be constructed offline.** Not for lack of data: **the treatment was never administered** | `evobot_lead_curator_measure_20261112/` |
| Adoption | **0.** 295 branches scanned, full history: **0** contain any file invoking a skill entrypoint. **819 commits**, 2104 distinct `.py`, 206 distinct `.sh` — **0 invocations**. 100 files authored after the skills existed → **81 external** → **0 invoke a skill** | same |
| **The cause — there is no load path** | No `CLAUDE.md` / `AGENTS.md` / `.cursorrules` / `GEMINI.md` / `.claude/` anywhere. **Nothing in the codebase reads `development_skills/`.** The repo README mentions it **0** times. The only two docs naming it carry status reports and one explicit warning *not* to count the 42 tests as an achievement — **none tells an agent to load or run a skill.** No agent had a reason to open the directory, and none did | same |
| Shape B is also absent | all **12** A/B experiments in `setup/acceptance` compare **robot** configurations; **0** compare development practices. There is no pair of comparable episodes differing only in skill availability | same |
| What the Curator refused to do | **did not manufacture a proxy.** Two offline measurements were reported **explicitly labelled as ceilings, not effects**: detector coverage (preflight 2/6 of its own cited cases; evidence-level-audit 0/1 on the bug that actually recurred) and practice drift on the `pkill` bracket trick (5/20 → 3/12, **not an effect** — the trick predates the skill) | same |
| The one real improvement, still not an effect | archived `interface_check.log` went **0 → 20**, all `INTERFACE_CHECK_OK` — but that gate is `benchmark/tools/check_ros_interfaces.py`, authored **01:46**, *before* the skills at **02:10**. **Pre-existing tool, not the skill** | same |
| What is missing, in dependency order | (1) **a load path** — one line in an agent-read instruction file pointing at `registry.json`, ~5 minutes; (2) a recurring task class (9 instances ever, 4 post-skill); (3) a per-episode outcome variable; (4) two-arm assignment | same |
| Power | detecting 50%→10% needs **n=14/arm**; 40%→10% needs **n=22**. Against **9 total episodes**, the smallest credible experiment is **~28 episodes — about 3× the entire history** of that task class. **It cannot be run by waiting for natural work** | same |
| The Curator's own discipline | it got two of its own numbers wrong in draft (3809→819 commits, 2118→2104 `.py`), **corrected them in a recorded section rather than editing quietly**, and re-ran the headline afterwards | same |

**The honest conclusion about the Curator role**: it is not that Development Skills do not work — **they have never been
tried.** A permanent measurement role with no load path can only ever report zero, and zero adoption is not
evidence of ineffectiveness.

**Prerequisite before the role can measure anything: add the load path.** Until then this role's correct output is
the one it produced — *"adoption is 0, here is what is missing"* — and not a plausible substitute.

---

## ADDENDUM — goal round 65 (2026-11-12): pinned-file invariant VERIFIED, and the drift predates this session

An integrity check flagged that `benchmark/evaluators/evaluate.py` was touched within 12 hours. Identified:

```
4fd36cd6  2026-11-12 01:04:34 +0800  sca331613-commits
  fix(t08): the evidence verifier rejected every valid push because evaluate.py never passed limits
  benchmark/evaluators/evaluate.py                 | 27 ++++++++++++-
  benchmark/evidence/test_evaluator_integration.py | 48 ++++++++++++++++++++++++
```

| Fact | State |
| --- | --- |
| **Who modified the pinned evaluator** | commit **`4fd36cd6` at 01:04:34**, author `sca331613-commits` — **the previous session, not this one** |
| When this session began | **~06:33** (simulator lock timestamp); first commit of this session is later still |
| **Pinned-file edits by THIS session** | **ZERO.** Verified across all 9 pinned files: none modified by any commit under this session |
| Live hash vs pinned hash | live `441903f1…`, pinned `ed4a6332…` — **still mismatched**, as recorded in the round-62 correction |
| So the drift is | **inherited, not created here.** It is the stale pin identified in round 62, and the evaluator it fails to describe was legitimately extended by the prior session at 01:04 |

**What this confirms**: the mission's prohibition on frozen-file edits without human approval was **held by this
session**. The one drifted pinned file was modified seven hours before this session's first action, by an earlier
author, with a commit message describing the reason.

**What it does not resolve**: whether that 01:04 modification had human approval is **not recorded anywhere I can
find**, and the baseline was never re-pinned afterwards. That remains one of the three decisions owed to a human.

**The fix location is unchanged from round 1** (`place_server.py`, the release predicate — not the contract), but it now has a mechanism, a frequency, a historical reach and a cost attached. **Still NOT applied: `place_server.py` is a frozen skill contract.**

---

## ADDENDUM — WorldState acquisition follow-up (2026-11-12, isolated cloud environment)

Source: `setup/acceptance/evobot_worldstate_probe_20261112/README.md`, its retained
raw captures, `analysis.json`, and `analyze_probe.py`. Base source `30fa2066`;
new environment, **not pooled with the preceding nine same-condition runs**.

| Fact | State and evidence |
| --- | --- |
| WorldState stream acquired | **CONFIRMED** — one Gazebo instance, 34 usable topic snapshots with 34 distinct source stamps over 19.785 s, and 34 identical action-result copies. Median gap 0.590 s, max 0.781 s, maximum reported object age 0.137 s |
| Earlier durability-mismatch hypothesis | **CONTRADICTED for this source/runtime** — actual publisher RELIABLE/VOLATILE; publishes only when `/observe` executes. Passive window: 0; active Observe: 34. TRANSIENT_LOCAL nearby in source belongs to CarryState subscription. Historical installed-source identity was not retained, so do not overstate retrospective certainty |
| `/tf` interpretation | **CORRECTED** — constant parent-relative link translations do not imply no world-frame motion. tf2 composition in WorldState shows EE x 0.19068–0.29134 m and z 0.01971–0.18750 m |
| Failed retreat is necessary for reverse motion | **REFUTED in this run** — first retreat's MoveToPose returned SUCCEEDED, reach error 6.296 mm, while bracketing red x moved 0.214850→0.247365 m. Second approach moved it further backwards; second retreat also reversed it. Exact finger/contact identity and reach-error contribution remain UNKNOWN |
| Actual end state | **FAILED** — red x 0.220000→0.279444 m, signed displacement along requested −x = **−59.444 mm**. Blue movement 0.0 m. Driver `achieved=+5.141 mm` is a positive per-attempt accumulation, not final net displacement; PushObject's displacement sample precedes its own retreat |
| Missing evidence | **CONFIRMED omission by this follow-up** — Push node `push.jsonl` was not retained: legacy profile has no push_server log_dir entry and the container fallback directory was not mounted. MoveToPose endpoint records, phase feedback, raw WorldState and both push results WERE retained. Future reproduction command now mounts the fallback directory |
| Full independent task acceptance | **FALSE** — unchanged evaluator reports terminal failure plus missing complete physics/contact evidence bundle; no new success or physical capability claimed |
| Frozen files / source changes | **UNCHANGED** — nine session-start frozen-file hashes preserved, inherited stale evaluator pin not refreshed. Added diagnostic tool, ROS verification and this new evidence archive; recovery policy and push contract unchanged |

Acquisition is **CAPTURED**; new robot capability **NONE**. T08 remains
`CALIBRATION_UNSUPPORTED`; L4 has not been acquired. Goal remains active.

---

## ADDENDUM — opt-in safe reposition development and one full candidate pass (2026-11-12)

Source: `setup/acceptance/evobot_safe_reposition_20261112/README.md`,
`result_summary.json`, read-only `analyze_results.py`, and 205 hash-verified raw
files in `raw_runs.zip`. Scope: isolated development from `fa08d8fe`, not a baseline
promotion or Runtime-autonomous L4 experiment.

| Fact | State / scope |
| --- | --- |
| Next-stage development plan | **RECORDED** — `docs/T08_DEVELOPMENT_PLAN_20261112.md`; public stage tracker #235; four open Junior work packages #231–#234, no individual assignee invented |
| Implemented candidate | **IMPLEMENTED + UNIT TESTED** — opt-in lift/transfer/lower adapter for approach/retreat, fresh EE measurement, measured clearance/carry guards, cancel and failure refusal. Defaults off. Existing core push contract, targets and thresholds unchanged |
| Physical candidate | **SIMULATION TESTED on one dev instance** — seed2000, two pushes; final signed −x displacement **+110.145 mm**, protected movement 0.0 m, all nine frozen acceptance gates true, evidence_status COMPLETE |
| Original control | **FAILED** — same copied world SHA, image, task and validator; final signed displacement **−63.655 mm**, peak lift 27.051 mm; terminal/table-support/no-lift gates fail |
| Candidate path evidence | **CONFIRMED** — all four routes execute LIFT→TRANSFER→LOWER; eight high endpoints ≥199.465 mm against the declared 187.791 mm minimum. First return adds 2.657 mm forward motion; second loses 0.625 mm. Both satisfy the preregistered 5 mm intermediate return-loss bound |
| Candidate independent physical evidence | **CONFIRMED for this one run** — 7,401 native physics steps/object, consecutive 5 ms intervals, zero dropped trajectory samples, measured pusher contacts, peak red lift 3.350 mm, gripper travel 1.583 mm under unchanged 2 mm limit, no attachment/teleport |
| Per-request push control | **NOT FIXED** — both individual PushObject calls still FAILED: contact loss then a ~17.5 mm overshoot. The final task's broader frozen band/zone passes; do not relabel the failed stroke contracts |
| Net-state accounting | **NOT FIXED** — old driver reports +107.524 mm while actual final net motion is +110.145 mm. Post-return measured state and bounded finishing are next-stage work |
| Acquisition failure | **INVALID_INFRA, retained** — initial candidate session sent no push. Outer preflight ended before the recorder's request timeout. One acquisition-only retry used a separate domain/output and longer outer budget; motion source unchanged. Underlying unanswered-goal cause UNKNOWN |
| Ordinary task regression | **NOT CLEARED** — candidate-overlay normal smoke fails at PLACE; original-source diagnostic also fails at PLACE. Both: carry release confirmed, gripper_open reached_goal=false/stalled=true/GRASP_STALLED, error 25. PICK passed. Audited source matches; release-related modules byte-identical. This reproduces the documented baseline release blocker, not proof of universal non-regression |
| Agent claim accuracy / False Success rate | **NOT MEASURED** — probe did not provide an Agent claim. Passing candidate's raw false_failure=true is a missing-claim artifact; a default false_success flag is not a measured zero rate |
| Source and authority | **HELD** — nine frozen hashes and contracts/push.py unchanged, no shared install edits, no gate adjustment, main merge, PR, hardware or paid model call. Detailed issue drafts were blocked by automatic approval review; safe generic work packages were published instead |

One successful candidate/control pair is **not** a success-rate, superiority or
generalization result. It demonstrates an actual return-path implementation and
one fully graded development task. Keep the opt-in candidate, preserve all failures,
and continue isolated state/finishing work. The ordinary release regression must
be resolved before formal promotion. Formal T08 remains `CALIBRATION_UNSUPPORTED`;
L4 has not been acquired. Goal remains active.

---

## ADDENDUM — measured feedback and fixed repeated T08 batch (2026-11-12)

Source: `setup/acceptance/evobot_push_feedback_20261112/README.md`, preregistrations,
exact v1/v2 source snapshots, `result_summary.json`, `run_analysis.json`, and the
hash-verified raw archive. Isolated engineering from `4746a637`, no Runtime Agent
autonomous-development experiment and no formal baseline promotion.

| Fact | State / scope |
| --- | --- |
| Post-return feedback | **IMPLEMENTED / TESTED / EXECUTED** — signed net position anchored to task start, fresh Observe after measured arm quiet, 30 mm request/5 mm overdrive/one increment, maximum three attempts; stop on known geometry, not a claim of independent acceptance |
| V1 development pilot | **FAILED / RETAINED** — final physical net **−86.016 mm**. Last online snapshot was **−56.489 mm** before further reverse motion; the v2 preregistration's shorthand cited that snapshot. Correction is retained explicitly, not a rewritten original. About 99 mm reverse movement aligns with a second retreat LOWER interval |
| V2 development pilot | **FULL TASK FAILED / MECHANISM GATE PASSED** — final **+11.375 mm**, complete return losses within 5 mm; second stroke reverses and third approach fails reach. Pilot data is separate from the fixed batch |
| New return mode | **EXECUTED** — optional LIFT→TRANSFER high hold on RETREATING, next APPROACH still includes LOWER. The frozen original low retreat target is honestly reported **unreached**, not faked successful. Defaults false; actual motion failures retain refusal/cancel behavior |
| Fixed repeat batch | **CONFIRMED on exposed seed2000 only** — all six predetermined slots A1 B1 B2 A2 A3 B3 completed, no infrastructure failures or replacements. Previous recovery **0/3** full passes; combined v2 **3/3**, final net **+61.558 / +50.537 / +76.131 mm**. Same image, TaskSpec/world/validator and three-attempt cap, five actual PushObject calls per arm. This measures the combined treatment, not individual component effects or statistical superiority |
| Candidate physical evidence | **FULL PASS, each 9/9** — native 5 ms consecutive traces, valid pusher contacts, protected/no-lift/support/gripper/no-attachment/no-teleport gates. Worst completed candidate return loss 1.678 mm. All candidate decisions stop at measured goal geometry before another push |
| Per-stroke control | **NOT FIXED** — all five candidate primitive calls in the fixed batch still FAILED their narrower stroke contracts. Under-delivery and overshoot remain; bounded request does not imply bounded physical displacement |
| Ordinary regression this turn | **PASS, one normal smoke** — PICK→PLACE→VERIFY, position error 10.766 mm within unchanged 60 mm tolerance, zero identity mismatches and zero model calls. Reposition modes default off in this launch |
| Prior release failures | **RETAINED / NOT RESOLVED BY ONE PASS** — previous candidate and original-source normal failures remain. No place/release source changes. Broad release consistency/non-regression is not established |
| Source / evaluation integrity | **HELD** — nine frozen files and push core match session start/30fa2066, actual v2 motion source hashes match preregistered sources, six related motion/release modules unchanged. Existing stale pin not refreshed. 95 relevant unit checks and four explicitly synthetic ROS protocol checks passed; test counts are not physical ability evidence |
| Agent claim accuracy / False Success | **NOT_MEASURED** — no Agent claim supplied; default false flags and false_failure on passing probes are harness artifacts, not measured claim accuracy |

This adds evidence of repeated **task completion on the current development
instance**, beyond the earlier single pass. It does not establish unseen-instance
generalization, precise stroke control, release reliability, or L4. Formal T08
remains `CALIBRATION_UNSUPPORTED`; baseline NOT_PROMOTED. No held-out task,
hardware, paid model call, main merge, PR or release. Goal remains active.

---

## ADDENDUM — architecture/contact audit and initial-world repair (2026-11-12)

Source: `docs/ARCHITECTURE_REVIEW_20261112.md`,
`setup/acceptance/evobot_contact_arch_audit_20261112/` and its preregistrations,
native-record audits, geometry pair and initialization-only Gazebo evidence.
Base d87f1701; this does not replace or pool the prior fixed B1/B2/B3 batch.

| Fact | State / scope |
| --- | --- |
| Contact flag interpretation | **CORRECTED** — contact_made=false is displacement-floor based, not absence of collision. B1's first stroke has 140 native pusher-contact steps despite the false flag. Withdraw the general inference “contact=False means no physical contact”; unreviewed historical attempts remain unclassified |
| Direction vs contact | **CONFIRMED observation, not unique cause** — pilot2's second stroke has actual EE +62.6 mm, object −16.9 mm, EE backslide about 0.1 mm. Five fixed-batch strokes show substantial top contact and changing pitch. Arithmetic direction error alone cannot explain that case; friction/mesh/attitude contributions remain UNKNOWN |
| New geometry pair | **COMPLETED, no infrastructure replacement** — G0/default EE 20 mm: +106.664 mm, full 9/9 PASS, 0/2 primitive passes. G1/EE 55 mm: 0 mm, full FAIL (terminal/pusher_contact), 0/3 primitive passes and no native pusher-contact steps in its stroke intervals. Default remains 20 mm; 55 mm proxy REJECTED; no repetition batch earned |
| Physical evidence distinctions | G0 **COMPLETE/PUSHED**. G1 raw verifier says **INCOMPLETE_OR_INVALID_EVIDENCE/UNKNOWN**; its trajectory and other gates pass, but terminal/contact fail. Actual zero-motion execution is retained, not relabeled as a missing-log infrastructure failure. No known acceptance false rejection confirmed in this pair |
| Initial-world adapter | **IMPLEMENTED / GAZEBO VERIFIED for a synthetic fixture** — new task_world materialize/verify only sets model initial poses before launch, preserves non-pose physics, refuses unsupported models/shapes/frames or invalid declarations, validates measured xyz/yaw. No TaskSpec edits or live pose mutation |
| Initial-world measurement | Two declared new xyz/yaw poses match Gazebo truth (about 2.5e−9 m position error); the old default scene is rejected. No pushing/moving task goals; no task grader/capability claim. Later CLI reproduces the measured world byte-for-byte; executed algorithm snapshot retained |
| Runtime integration | **NOT COMPLETED** — composites already dispatch native PUSH and have postcondition checks. The new feedback CLI is not called by the decision/executor loop; its direct engineering expected_goal input is not the Agent public boundary. Logged retreat_failed has no matching PushObject ROS result field |
| Autonomous development | **NOT ACQUIRED** — proposal generation/gating is not an apply/build/Gazebo/accept loop. Synthetic reproduction shows re-generation of a superseded release-retry idea; generic offline guard task published as #236. No proposal or carry-ack-only release semantics was applied |
| Verification / invariants | 95 relevant existing unit checks, 5 frame checks, 8 initializer checks, 4 synthetic ROS protocol checks PASS. Nine frozen files, core and nine related motion/release modules unchanged. Actual pair sources match preexecution; old native hashes match the prior published archive. Ordinary pick/place NOT_REPEATED_THIS_TURN; prior outcomes retained |
| Agent claims | **NOT_MEASURED** — no Agent claim supplied; no false-success-rate inference from default flags |

The initialization seam is usable; unified-runner integration and unseen manipulation
are still pending. No new reliable bounded-stroke capability claimed this turn.
Prioritize actual contact modeling, constrained motion and explicit post-return
state, then Runtime integration and frozen regression/unseen tests. T08 remains
CALIBRATION_UNSUPPORTED; formal baseline NOT_PROMOTED; L4 NOT_ACQUIRED. Goal active.


---

## ADDENDUM — finger TCP, constrained strokes and returned receipts (2026-11-12)

Source: `setup/acceptance/evobot_contact_motion_20261112/README.md`, statistics,
all 15 executed sessions, preregistrations/source snapshots and hash-verified raw
archives. Base6186271b. Isolated engineering; no autonomous Runtime development
experiment or baseline promotion.

| Fact | State / scope |
| --- | --- |
| Real finger TCP | **IMPLEMENTED / PHYSICALLY CHECKED** — actual pinned collision triangles and native world link5+126mm EE transform; selected left-finger patch, lateral offset and fixed85° pitch. Ground-truth contact-to-patch error max0.050mm across final six strokes |
| Bounded new adapter | **CONFIRMED ON EXPOSED INSTANCE/TASK-SCOPED GRAPH** — K1 development validation plus fixed K2/K3 confirmations: six30mm requests pass unchanged push.judge; returned signed distances30.480–30.494mm; final nets **60.974 / 60.972 / 60.975mm**, each full9/9 PASS. Existing PushObject action/server remains unchanged; these are new adapter receipts |
| Actual tracking | **NATIVE5ms CHECKED** — no simulation-step gaps; worst TCP lateral/vertical9.2µm, pitch0.0041°, tool floor clearance about2.000mm. Knot/midpoint screening is not a continuous arbitrary-spline collision proof |
| Returned interface | **EXECUTED / LIVE-CONSUMED** — six completed stable returns with arm_ready and returned-request geometry true; all six accepted on timely ROS reception and refused300ms later. Stroke outcome, return completion and unknown terminal remain separate. Revision equality is not a pose-invariance guarantee |
| Same-graph control K0 | **FULL PASS / PRIMITIVE FAILED** — old30mm request moved47.948mm in frozen primitive log and failed overshoot. Final physical net46.097mm; earlier online snapshot46.257mm is not final. Do not claim final-task superiority or pool old/default-graph D1 |
| Development failures | **RETAINED** — pilot1 unknown terminal; pilot2 two bounded strokes/full task PASS but second return unusable; B1/C1/E1/F1/G1/H1 state/telemetry refusals; I1 bounded stroke with return-preparation failure; J1 strict-stop cancellation; D1 full default-graph control FAIL. Unearned confirmation slots NOT_RUN. No replacements |
| Resource/scheduling | **PARTIALLY ADDRESSED IN ISOLATION** — CPU quota2; pure planning moved to worker, source/frame joins corrected, fresh actuator admission retained. Final harness removes four unused services only. Full default Runtime source pauses remain unresolved; no blanket real-time reliability claim |
| Cost | **NOT IMPROVED** — final candidates24 actuator goals/2 requests, event spans370/460/427s; same-graph K0 six goals/1 request/~35s. Precision and safe returned state are the gain, not throughput |
| Verification/integrity | **HELD** —162 relevant unit checks,7 explicitly synthetic real-ROS protocol checks, isolated package build/imports, all executed source hashes match preregistrations. Final geometry comment alone corrected; five runtime ASTs match execution. Nine frozen files, push core and10 existing modules unchanged; no TaskSpec/threshold/default-launch change |
| Ordinary tasks/unseen/Runtime | **NOT_RUN / NOT_INTEGRATED** this round. Prior mixed release outcomes retained. Adapter supports pinned upright35mm boxes/world−x only and engineering expected_goal input |
| Agent claims | **NOT_MEASURED** — no Agent claim; default false flags are not claim-accuracy evidence |

This is a scoped new bounded-push/returned-state development capability. Do not
promote it into a reliable general robot skill or L4 claim. Formal T08 remains
CALIBRATION_UNSUPPORTED; baseline NOT_PROMOTED. Goal active.


## 2026-11-12 — Public Runtime integration and environment-loss checkpoint

Base8c3972da; isolated reconstructed recovery candidate. Previous physical
contact results are retained separately, not reclassified as Runtime evidence.

| Item | Verified status |
|---|---|
| Public Runtime implementation | CANDIDATE: bounded rule planner, typed ContactPush action, default-off TaskFSM registration and post-return admission. No LLM or autonomous Develop claim |
| Local build/checks before loss | Interfaces/skills built;117 focused checks passed. Extended selection309 pass/10 old PickServer fixture errors. Does NOT validate reconstructed revision; #238 requests independent baseline reproduction |
| R0 control | INVALID_PHYSICAL_CONTROL: missing required contact-height declaration, no motion; retained failure |
| R0b corrected control | UNKNOWN: motion started; managed environment disconnected before final result/evidence could be read |
| New local candidate/probe | NOT_RUN: R1/R2 had not executed before environment loss |
| Recovery source | RECONSTRUCTED through GitHub from pinned parent and tool-visible code, not claimed byte-identical to tested local worktree |
| Recovery acceptance | New isolated CI build/test and fixed CI_L0/CI_C1/conditional CI_C2 window prepared; only actual CI records may establish results |
| Capability/status | NOT_PROVEN_THIS_CHECKPOINT; formal baseline NOT_PROMOTED; L4 not crossed; T08 formal status remains CALIBRATION_UNSUPPORTED |
| Infrastructure | #237 open; environment interruption is not a demonstrated cause of full-graph scheduling stalls |
| Evidence/cleanup | Original raw logs/worktree inaccessible. No invented raw archive. Original container/process cleanup UNKNOWN |
| Frozen boundary | Reconstructed candidate preserves parent9 frozen files, push arithmetic, old TaskSpecs and default launch; CI independently checks hashes |

Evidence/status source:
setup/acceptance/evobot_runtime_push_20261112/README.md and
recovery_observations.json. CI success, if obtained, needs a separate append.


## 2026-11-13 — Public Runtime task execution confirmed; raw evidence recovered

This supplements the environment-loss checkpoint above. It does not erase its
then-UNKNOWN state or pool earlier engineering-driver runs into Runtime results.

| Item | Current verified status |
|---|---|
| Actual execution source |22f873bae82ce61270a63397fbecdd3a119a115e, CI43274720654, immutable during all slots |
| Public original red-block task |CONFIRMED: Runtime completed2 stages,24/40 actuator goals,162.08/600s; frozen full9/9 PASS; final signed-x60.9318mm |
| Public blue-object probe |CONFIRMED: same implementation, changed target/start/region;2 stages,24 goals,171.57s; full9/9 PASS; final signed-x60.9383mm |
| Returned-state interface |LIVE_CONSUMED:4 correlated real action results with completed returns/arm readiness; recorded receipt ages26.5–107.1ms; replay contract passes all4 |
| Claim agreement |Both Runtime claims agree with independent full physical acceptance; false_success=false in both |
| Legacy CI_L0 control |Runtime postcondition failure63;2 zero-duration contact intervals rejected by recorder. INVALID_EVIDENCE; excluded from physical success-rate comparison; #239 |
| Recovered local R0/R0b |R0 invalid zero-motion control; R0b now CONFIRMED Runtime failure62 and full acceptance FAIL. Former UNKNOWN superseded only after recovery; separate earlier image/source |
| Integrity/replay |Original18,526,560-byte ZIP SHA33fbead803028d16d451c180e5d0a80c18bd28c5825b9e8f4607bd10db13d28c; all306 manifest files and complete coverage match; unchanged source/task hashes; independent raw replay reproduces both9/9 passes |
| Build/checks |New revision built interfaces/skills, compiled harness and passed289 relevant checks. No full-regression claim; old fixtures #238 remain open |
| Boundary |ONE trial per current Runtime task; blue probe is development-declared, not formal held-out. No statistical superiority, broad repeatability, ordinary-task regression closure, transfer or L4 claim |
| Defaults/formal status |Legacy remains default; formal baseline NOT_PROMOTED; T08 formal CALIBRATION_UNSUPPORTED; main goal active |
| Cleanup |After environment recovery current selected environment has0 owned containers/simulator processes. CI --rm container/job completed; full-graph scheduling issue #237 not resolved |

Evidence:setup/acceptance/evobot_runtime_push_20261112/README.md,
results.json,offline_verification.json,archives.json and both permanent raw ZIPs.
The next capability gate is fixed Runtime repetitions plus ordinary physical
regression before wider inputs and formal held-out evaluation.
