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
| The aperture signal can distinguish grasp from no-object | **NO — and this is the important limit.** G1 (grasp) 11.71 mm vs G3 (nothing present) 12.13 mm differ by **0.4 mm**; effort pinned at 10.0 and `stalled=False` in both. The gripper never stalls on the 35 mm block, so travel says only *"the gripper fully actuated"*, not *"it was holding something"*. It separates grasp from **push**, not grasp from **air**. A fail-closed anti-pick-carry gate therefore needs the **lift** signal too (97.4 mm here), not the aperture alone | same |
| T08 skill-level capability | **NOT ACHIEVED** — 0/6 on unseen, 0/5 dev closed-loop; the primitive has never satisfied its own contract on any batch | both batches |
| Contact-height calibration (task-9) | **NOT_RUN** | task-9 |
| L4 Develop | **NOT CROSSED** | — |

### Round 3 corrections to the Lead's own record

1. **Withdrawn:** "no task in this benchmark has ever been instantiated at its declared pose" — true of 5 T08 specs, not of the benchmark.
2. **Withdrawn:** "the backwards flick is the end effector failing to hold a contact face" — contact geometry does not predict the flick.
3. **Disclosed:** one commit (`59a9d7f5`) accidentally included 145 MB of derived evidence; the next commit compressed and excluded it (`86f78f2d`), and the oversized blobs remain in history because force-pushing a shared branch is worse than the storage cost.
4. **Disclosed:** a test (`never touches a model that is not in the spec`) required narrowing because the zone-marker behaviour changed **on purpose**; the narrowing is documented in the test and the zone behaviour gained 3 tests of its own rather than losing coverage.
5. **Disclosed:** I first read `calib_G1` while the lane was still re-running it and recorded "the grasp lifted 0.000000 m" as a confirmed fact. The final file (1257 samples, not 1171) shows a **97.4 mm lift** — the grasp succeeded. That row was corrected here rather than left standing, and it is a reminder that a file being present is not the same as a run being finished.