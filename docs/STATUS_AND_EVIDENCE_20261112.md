# EvoBot — Current Status & Evidence Navigation

**GitHub issue #234 · 2026-11-12** · branch `autonomous/flexcell-remediation` · HEAD `8946e9cf`
**A map, not an audit.** Every number carries a source and a scope; where the source does not settle it, the entry
says **UNKNOWN**. Append-only detail: `docs/FACT_STATE_20261112.md` — read it before quoting any figure.

## 0. The single most important distinction

The project holds **two things routinely read as a capability. Neither is one.**

| Item | What it actually is | What it is NOT |
| --- | --- | --- |
| **An explanation of the T08 push defect** — the fingers arrive **21.7 mm above the box top** because `contact_height_m` is commanded against `end_effector_link`, which sits **44.3 mm ahead of** the finger joints; the executed motion is a friction drag across the top face, which has no fixed direction | An **explanation**, supported by geometry (URDF), statistics (204 archived approaches) and camera frames | Not a robot capability. Not a fix. Not independently verified |
| **A candidate fix** — a "staging move" that changes the arm's pitch before the push | A **candidate measuring 17/18 across six seeds**, claimed in a commit message; its artifact-backed sibling result is **10/10 task passes** (§5) | **Not independently verified.** The evaluator was not run, the injection pipeline is not a sealed harness, and the staging move can silently fail to take effect |

**Say exactly that, in that order, every time.** The explanation and the candidate are the round's real output; the capability is not.

## 1. Navigation — where authority lives

| Purpose | File | Status |
| --- | --- | --- |
| Master goal (round authority) | `docs/EVOBOT_MASTER_GOAL_20261112.md` | PRESENT |
| Higher authority | `docs/EVOBOT_NORTH_STAR_MISSION.md` | **§8–§14 TRUNCATED → `BLOCKED_MISSION_TEXT_MISSING`**; nothing may be inferred |
| §8–§14 extract | `docs/EVOBOT_NORTH_STAR_MISSION_S8_S14_AUTHORITATIVE.md` | PRESENT |
| **Fact state — what may be quoted** | `docs/FACT_STATE_20261112.md` | append-only |
| Capability ladder | `docs/CAPABILITY_LADDER.md` | generated, never hand-edited |
| Agent instructions | `AGENTS.md` | PRESENT |
| Development Skills (UNMEASURED) | `development_skills/registry.json` | all four `PROPOSED` |

## 2. Implementation state, in five separate buckets

Per acceptance criterion 1. A row may appear in several buckets; buckets are never merged.

| Bucket | Contents |
| --- | --- |
| **Code implemented** | `inject_instance_poses.py`; staging candidate `candidate_staged_push.py`; `push_recover.py`; 9-gate evidence verifier; re-observe-after-push in `goal_check.py` |
| **Synthetic / unit tested** | `benchmark/evidence/` **75 passed**; `test_evaluator_integration.py` **10 passed**; instance-pose injection **7 passed**. (`INTEGRATION_PROCEDURE.md`'s 73 and 8 are **stale** — FACT_STATE §3) |
| **Simulation executed** | T08 dev + held-out pushes in real Gazebo; staged-candidate batch (10 committed records); the T04 instance; the 16-run reversal study; the 204-approach aggregate |
| **Complete independent acceptance** | **Very little.** `S/t3` reached `passed=true` with a complete same-run bundle, all 9 gates true (§4.0d) = **Simulation Tested, 1 instance, 1/5**. B baseline 9/9 was graded by the frozen evaluator; the legacy A′ comparison was **mislabelled** (§4) |
| **Not executed** | Genuine A′/B paired execution (`evobot_p0_paired.sh` **never compiled**); closed-loop C; any real-hardware run (prohibited); the 17/18 six-seed batch **has no committed artifacts** (§5) |

## 3. T08 push — what is established

| Fact | Value | Source | Scope |
| --- | --- | --- | --- |
| Fingers above the box top | **21.7 mm** measured; **median 21.3 mm across 204 archived approaches, 90 % above at all** | FACT_STATE rounds 24/27/30 | archived approach orientations |
| Cause | `end_effector_link` **44.3 mm ahead** of the finger joints; `contact_height_m` targets the ee frame | `open_manipulator_x.urdf` + one archived `move_to_pose` record | **one record, not a distribution** |
| Reversal rate | **7 of 16 = 44 %**, cosine ≈ −1.000, `contact_made` true | 16 single-shot runs | single-shot arm only |
| `contact_height` sweep | 0.0150–0.0250 all produce **both** outcomes | height-sweep batch | **excluded as a fix class** (−26.7 mm needed vs a 10 mm scan) |
| First `passed=true` ever | `S/t3`, single-shot, 9/9 gates, PUSHED, gripper travel 0.0133 mm | FACT_STATE §4.0d | **1 instance, 1/5** |
| Correct T08 label | **"Simulation Tested — T08 push, 2 clean held-out instances (n=2), zero false success."** | round 51–52 addendum, after independent review | post-hoc denominator excluded |
| Staged candidate | **10/10 task passes, 10/10 direction-correct** — recomputed here from committed `cand_*.json` | commit `9663abee` | **1 seed, same-condition batch** |

## 4. Baselines — what may and may not be compared

| Group | State |
| --- | --- |
| **A (oracle)** | A-v2 **71/72 = 98.6 %**, False Success 0. **A-v0's 44/72 INVALID** (136-orphan leak). Re-grading 72 observations with v0.5.0 reproduces **72/72 verdicts, 0 disagreements** — but the archive **mixes evaluator versions 0.2.0/0.3.0/0.4.0**, so it is not one instrument |
| **A′ (rule planner)** | **72/72 at PLAN LEVEL ONLY — never executed.** Rules written after seeing the templates. **"A′" is ambiguous: three implementations carry the name**, one declining 100 % of T01–T06 |
| **B** | v2: 17/18 planned. **Real execution 9/9, False Success 0** |
| **"A′ vs B" paired table** | **MISLABELLED — the "A′" column is the ORACLE's output** (byte-identical regeneration; the real rule planner disagrees on T06). Oracle-vs-B, near-tautological. **Goal §6.4 gate NOT closed** |
| **C / D** | C **not run as a closed loop** — its lesson set is empty because the planner is never wrong in the archive (0 of 211 runs). D **UNDEFINED** — proposed definition only |

**Cross-environment pooling is forbidden.** Plan-level, simulation and (non-existent) hardware results are never pooled into one statistic.

## 5. Provenance gaps found while writing this page

| Claim | Committed artifacts? | Standing |
| --- | --- | --- |
| Staged candidate **10/10** | **YES** — 10 run JSONs under `setup/acceptance/evobot_lead_t08_calib_20261112/staged_candidate_20261112/runs/` | Recomputed here: **10/10 passes, 10/10 cos ≥ 0.9**. Artifact-backed |
| **17/18 across six seeds (94 %)** | **NO** — commit `7bbe590b` is an **empty commit, 0 files changed** | **Commit message only.** Not verifiable. Quote only as "claimed in `7bbe590b`, not independently checkable" |
| **11/15 (73 %) and its retraction** | **NO** — `7bfb14fd` and `9268af8b` are both **empty** | Both withdrawn anyway; do not quote the 11/15 |

```
$ git diff --name-only 7bbe590b^ 7bbe590b | wc -l   ->  0
```

Not an accusation — the retraction in `9268af8b` is the discipline working. It is a **navigation fact**: a reader checking 17/18 will find nothing, and should be told so before they look.

## 6. Retractions — 14, already tabulated in FACT_STATE

| Where | Count | Content |
| --- | --- | --- |
| FACT_STATE → round-24 addendum → *"Theories this session raised and then refuted"* | **11** | ROS domain IDs; "arm cannot do T08"; "0/26 attempts"; "Generalization Tested n=3"; descent knocks the box; residual error; neutral-pose retry; `ec 27/28` as untrustworthiness marker; retreat transit as general cause; request 0.10 beats 0.09; `approach_clearance` explains reversal |
| FACT_STATE → *"Superseded entries in this file"* | **3** | Round-24 wording (superseded by measurement); round-25 "grip holds/slips" and "carried drag" **WITHDRAWN** (the gripper is never commanded); round-22 `approach_clearance` **WITHDRAWN** |

**Also withdrawn elsewhere in FACT_STATE**: "no task has ever been instantiated at its declared pose" (too broad — only `t08_dev` 2/3 and `t08_unseen` 3/3 affected); "blue block moved 0.030/0.010/0.050 m" (**the Lead's own error** — ground-truth motion was **0.000000 m**); "0/6 unseen" / "T08 fails to generalise" (**never measured**); the "8 of 15" figure; and the round-61 evaluator-"drift" alarm, **downgraded in round 62 to a stale pin**.

## 7. Must NOT be quoted as current

| Do not write | Why |
| --- | --- |
| "T08 fails to generalise" / "0/6 unseen" | Retracted — the harness never instantiated the declared poses |
| "A′ 72/72" as an execution or capability result | Plan layer only, never run |
| "The A′/B paired execution exists" | `evobot_p0_paired.sh` never compiled; no `paired.tsv` anywhere |
| "Recovery raises the T08 success rate" (2/5 → 4/5) | **Not supported at n=5: Fisher p = 0.5238.** Raw counts only, p stated |
| "T08 is Generalization Tested" | Label overturned by independent review; correct wording in §3 |
| "17/18" as a verified capability | Empty commit, no artifacts (§5); evaluator not run |
| `false_failure=true` as evidence of a defect | **Degenerates to `== passed` when no agent claim exists** — true on all 9 B runs, including the 8 clean ones |
| A-v0's 44/72 · the 42 Development Skill unit tests | Process leak (136 orphans) · test well-formedness, not effect; adoption is **0** |

## 8. UNKNOWN — cannot be confirmed from the record

- **Whether the 01:04:34 evaluator edit (`4fd36cd6`) had human approval.** Not recorded anywhere found. (This session edited **0** pinned files — verified across all 9.)
- **Whether `evobot_heldout_n6_20261111` has the same pose-instantiation defect.** Flagged, never checked. **Verify before quoting that result again.**
- **Whether the staging fix generalises beyond its seeds** — one known failure mode: a staging move that silently does not take effect; no guard exists.
- **The T08 variance mechanism beyond the staging story** — shape established, full cause not. **The T04 false-negative rate** — mechanism confirmed (H1), n = 1.
- **Whether the gripper gate can ever distinguish a push from a grasp** — it rejected two direction-correct pushes on finger deflection alone.
- **Mission §8–§14 content** — text truncated; nothing may be inferred.

## 9. Boundaries that do not move

No threshold lowering · no deleting failure evidence · no frozen-file edits without human approval · no main merge · no PR · no real hardware · no unsanctioned spend · no bypassing the LLM budget gate · no plan-level result quoted as an execution result · no sim result quoted as a real-robot result · **no Development Skill effect claimed for a robot capability** (adoption of the four `PROPOSED` skills is **0**; `setup/acceptance/evobot_lead_curator_measure_20261112/`).

**Level 4 Develop: NOT achieved. Level 5 Improve: awaiting human approval. Level 7 Transfer: not observed (cause found — 0 of 64 failures are planning-attributable).**
