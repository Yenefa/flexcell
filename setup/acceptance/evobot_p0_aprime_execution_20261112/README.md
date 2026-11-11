# A-prime execution: the 16 archived T14 runs, graded

**Auditor** gate-auditor · **Date** 2026-11-12 · **Task** task-12  
**Inputs** `setup/acceptance/evobot_crosstype_20261111/runs_T14_ordered_pair/`  
**Method** offline only. No Gazebo, no model calls. Frozen `evaluate.py` v0.5.0.

---

## 0. The finding that changes the task

**These 16 runs are NOT A-prime.** They are **arm B (deepseek-flash)**.

Evidence, from `agent_reply.json` in every run directory:

```
requested_model   deepseek-flash
base_url          https://api.deepseek.com
key_fingerprint   2caaf9b9
temperature       0.0
```

I also compared each archived `plan.json` against what the rule planner produces from
the same `observation_input.json`: **0 of 16 are identical**, and the difference is
systematic — B spreads the two blocks to distinct destinations inside the bin
(0.205 / 0.295 on the x-axis, or 0.075 / 0.165), while A-prime would place both at the
zone centre (0.25 or 0.12). That is B's `spread_destinations` post-processing, which
A-prime does not use.

So the archive contains **no A-prime execution at all**. Task-12's premise — "16 real
Gazebo runs for T14 already exist" — is true of *runs*, but they are the wrong arm.

## 1. Gradeability audit (the Lead asked me not to assume this)

**16 of 16 are gradeable. 0 dropped.** Ingredients verified per run:

| ingredient | source | status |
| --- | --- | --- |
| measured end state | `observation.json` / `observation_after1.json` | 16/16 |
| ground truth | `ground_truth.json`, `source: GZ_GROUND_TRUTH`, `errors: {}` | 16/16 |
| public spec | `benchmark/held_out/recovery_public80/<id>.json` | 16/16 |
| expected_goal | **sealed at `/etc/evobot/sealed`, root-only — NOT READABLE** | reconstructed, see below |
| frozen evaluator | `benchmark/evaluators/evaluate.py` v0.5.0 | present |

### The sealed answer: reconstructed, then validated

`/etc/evobot/sealed` is mode root-only and unreadable to this lane. Rather than stop, I
reconstructed `expected_goal` from the public instruction with the T14 template shape
(side word → zone by **measured** y, colour → object, FIRST/then → order), and then
**checked the reconstruction against the archive's own recorded answer**:

> **reconstruction agrees with the archived `order` clause: 16/16.**

That cross-check is what makes the reconstruction usable rather than a guess. It is
still a reconstruction, and it is flagged as such — not read from the seal.

## 2. Three numbers, kept separate

| metric | result |
| --- | --- |
| **planning_correct** | **16/16** |
| **execution_succeeded (first attempt, no recovery)** | **11/16** |
| **independent_evaluation_passed (first attempt)** | **14/16** |
| independent_evaluation_passed (after recovery) | 16/16 |

| run | planning | exec 1st | eval 1st | eval after | recovered |
| --- | --- | --- | --- | --- | --- |
| HO-0dcde4dc0f5a | ✓ | ✓ | ✓ | ✓ | no |
| HO-128c6a231c34 | ✓ | ✗ | ✓ | ✓ | no |
| HO-2efba46248da | ✓ | ✗ | ✗ | ✓ | **yes** |
| HO-40348a081df6 | ✓ | ✓ | ✓ | ✓ | no |
| HO-4dafd8d17858 | ✓ | ✓ | ✓ | ✓ | no |
| HO-4dbb21d087ae | ✓ | ✓ | ✓ | ✓ | no |
| HO-51600cf21179 | ✓ | ✗ | ✓ | ✓ | no |
| HO-60679893327a | ✓ | ✓ | ✓ | ✓ | no |
| HO-6173170d8c47 | ✓ | ✓ | ✓ | ✓ | no |
| HO-675c07e900e7 | ✓ | ✓ | ✓ | ✓ | no |
| HO-884ea68a42ca | ✓ | ✓ | ✓ | ✓ | no |
| HO-b3fb8b1de2db | ✓ | ✓ | ✓ | ✓ | no |
| HO-c79ebfe5c9e6 | ✓ | ✓ | ✓ | ✓ | no |
| HO-d3ab212142de | ✓ | ✗ | ✗ | ✓ | **yes** |
| HO-da7c04bdece5 | ✓ | ✗ | ✓ | ✓ | no |
| HO-dcf52d233154 | ✓ | ✓ | ✓ | ✓ | no |

### Why the recovery split matters

`observation.json` is the **final** state (after recovery). `observation_after1.json` is
the state after the **first attempt**. For 14 runs they are identical; for the 2 resumed
runs they are not. Grading only `observation.json` would report **16/16 execution** and
silently credit recovery to the first attempt.

Reading the recovery record also has a trap I hit and fixed: the record has **two
shapes** — a flat `{'action': 'no_recovery'}` when the first attempt was clean, and a
nested `{'decision': {'action': 'resume'}}` when it was not. Reading only the top-level
key reports the 2 resumed runs as "not recovered", which is exactly the error above.

**This is the round's clearest instance of the conflation the Lead asked about:**

> planning 16/16 ≠ execution 11/16 ≠ evaluation 14/16 ≠ evaluation-after-recovery 16/16

Any one of those quoted alone as "T14 scores 16/16" would be a different claim.

## 3. A-prime vs arm B on T14

| arm | planning_correct | model calls | execution |
| --- | --- | --- | --- |
| B (deepseek-flash) | **16/16** | 16 | 11/16 first-attempt |
| A-prime (rule planner) | **16/16** | **0** | **not run** |
| A-prime order == B order | **16/16** | | |

**On T14, A-prime matches the LLM's plan 16/16 at zero model cost.**

Per the Lead's instruction, this is reported as what it is: **B's measurable value on
these templates is zero.** That is a real, publishable negative result — not an
experiment failure. A deterministic parser reproduces the LLM's plan exactly on every
instance of this template, including the temporal ordering that T14 was built to test.

**What this does NOT show:** A-prime was never executed. "Plans correctly" is not
"task passes". A-prime could plan perfectly and fail in the arm — the same separation
the 11-vs-16 gap demonstrates for B.

## 4. What a fair A-prime-vs-B comparison requires

To make the comparison real, the following must all hold. **I am asking before spending
Gazebo time, as instructed.**

1. **Same instances.** Both arms on the same 16 T14 held-out ids (they exist).
2. **Same observation.** A-prime must consume `observation_input.json` byte-identically
   to what B consumed — it already can, and it produces the same order.
3. **Same executor path.** `run_composite_plan.py` → RunComposite, same
   `motion_profile_id`, `clearance_m`, `position_tolerance_m`.
4. **Same evaluator.** `evaluate.py` v0.5.0, unchanged, on measured ground truth.
5. **Report three numbers per arm**, never one: planning / execution-first-attempt /
   evaluation. Recovery reported separately, never folded in.
6. **Cost column.** A-prime 0 model calls; B 16. That is the point of the comparison.

### Gazebo budget requested (NOT started)

| arm | runs | notes |
| --- | --- | --- |
| A-prime on 16 T14 ids | **16** | zero model calls |
| B | **0** | already exists, re-graded not re-run |

**16 runs, no model calls.** If the sim lane holds `/tmp/evobot_sim.lock`, this waits.

## 5. What I could not do

| item | status |
| --- | --- |
| read the sealed answer directly | **BLOCKED** — `/etc/evobot/sealed` is root-only; reconstructed and cross-validated 16/16 instead |
| grade A-prime execution | **BLOCKED** — no A-prime runs exist in any archive |
| re-run B | not needed — 16 runs already exist and re-grade cleanly |

## 6. Reproducing

```
python3 setup/acceptance/evobot_p0_aprime_execution_20261112/grade_archived_t14.py
python3 setup/acceptance/evobot_p0_aprime_execution_20261112/three_numbers.py
```

Outputs: `grading/gradeability.json`, `grading/three_numbers.json`.

Nothing was executed, no simulator started, no model called, no frozen file touched.
