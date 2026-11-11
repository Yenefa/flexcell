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

**The fix location is unchanged from round 1** (`place_server.py`, the release predicate — not the contract), but it now has a mechanism, a frequency, a historical reach and a cost attached. **Still NOT applied: `place_server.py` is a frozen skill contract.**
