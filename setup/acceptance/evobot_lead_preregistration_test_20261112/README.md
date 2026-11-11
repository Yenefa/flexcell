# I rediscovered 2026-11-11's work, and testing it found a vacuous success criterion

**Date** 2026-11-12 · **Status: two process failures of mine, one substantive finding about a pending proposal**

---

## 1. Process failure: this was already found, fixed in design, and pre-registered

Round 3 of this session presented the `place` release defect as a new root-cause discovery. **It was not.**
On **2026-11-11** the same mechanism was established with 9 cases, the wrong earlier proposal
(`bounded_release_retry`) was explicitly superseded, and the correct fix was **pre-registered and is
awaiting human approval**:

```
evolution/proposals/release_confirmation_preregistration.json
  proposal_id : release_confirmation_over_gripper_aperture
  registered_at: 2026-11-11        registered_before_change: true
  approved     : false             status: PROPOSED - awaiting human approval, not implemented
  target_file  : .../place_server.py
  evidence     : setup/acceptance/evobot_release_mechanism_20261111
```

That directory contains a README with the identical field table, the identical signature, and the identical
conclusion. **I did not look, and presented a day-old finding as new.**

This is the same error class as the five I recorded in round 2 — resolving a name and inferring from it —
with a new twist: I checked whether the *code* had the bug, and never checked whether the *project already
knew*. `evolution/proposals/` and `setup/acceptance/evobot_release_mechanism_20261111/` were both one
`ls` away.

**Corrective, stated so it applies generally: before diagnosing a defect, search the proposal registry and
the acceptance archive for its signature.** This project keeps its own history in both, and P3's whole
purpose is that findings persist across sessions.

## 2. What my work does add (and it is not nothing)

| contribution | prior work | mine |
| --- | --- | --- |
| mechanism | 9 cases, cross-batch | same mechanism, independently confirmed in a **20261010** archive |
| frequency | 9 cases | **47 of 238 runs (19.7 %)**; 51 of 539 place attempts across 21 archives |
| causal test | not present | **pin releases predict the world state 16/16** — releases=2 → pass 13/13, releases=1 → fail 3/3 |
| the field that makes the fix trivial | `carry_release_confirmed` | verified present in the same record |
| **task-level impact** | predicted 2/32 false failures → 0 | **refuted: zero provable task-level false failures in 237 runs** |

The last row is the substantive finding and it is in §4.

## 3. The contradictory signal, verified directly

The preregistration's central claim is that one record contains two contradictory signals and the skill
trusts only the gripper. Verified in `c13_constrained_20261010/plate030-legacy/run-a915cba2c302`:

```json
{ "released": false,
  "carry_release_confirmed": true,        <-- the carry layer says the object WAS released
  "gripper_open": { "reached_goal": false, "stalled": true,
                     "position": -0.011, "aperture_error": 0.031,
                     "classification": "GRASP_STALLED" },
  "detail": "gripper did not open (position=-0.011 requested=0.02 stalled=True)" }
```

**`released: false` and `carry_release_confirmed: true` in the same dictionary.** The proposal is right, the
fix is correct in principle, and the data needed to implement it is already recorded.

## 4. Substantive finding: the proposal's task-level success criterion is vacuous

The preregistration's **prediction** includes:

```
"task_level_false_failure_rate": "6.2% (2/32) -> 0% on the same instances"
```

and its **success criteria** include:

```
"task-level false failure count falls to 0"
```

**I re-graded all 238 archived runs and found zero provable task-level false failures.** Of the 47 runs
hitting the defect, 28 were recorded as passing anyway, 8 have no verdict, and I tested all 11 recorded
failures against the failed clause's evidence and the ground truth:

```
candidates tested       : 11
provable false failures :  0
```

Every one is a genuine failure — in most, an object is **still sitting at its initial pose**. The task was
never performed, whatever the gripper did.

**Therefore: if this proposal were implemented and graded on its success criteria, criterion 2 ("task-level
false failure count falls to 0") would be satisfied by a number that is already 0.** It would look like
success and mean nothing.

That is exactly the class of defect this project keeps finding — a criterion that passes for the wrong
reason. Finding it **before** the change is approved is the point of pre-registration, and it is the one
thing my re-discovery genuinely contributed.

## 5. What the proposal should be credited with instead

The fix is still worth making, and its real benefit is narrower and precisely measurable:

| claim | status |
| --- | --- |
| `place` reports failure while the carry confirmed release | **real, 47/238 runs** |
| fixing it removes those **execution-verdict** failures | **yes** — `skill_layer_release_failures 9 -> 0` is a sound prediction |
| fixing it removes **task-level** false failures | **no — there are none to remove** |
| fixing it changes any pass/fail result | **no** — the evaluator grades the world, which is already correct |

**So the proposal's own anti-gaming rationale is the correct framing and the prediction is the part that is
wrong:** "reclassifying the self-report cannot make a failing world pass; it can only stop a succeeding
world from being called a failure" — and in the archive, there is no succeeding world being called a
failure at the task level. The benefit is confined to the execution verdict, which is exactly where
A-prime's 9/16 vs its own 13/16 evaluation lives.

## 6. Recommended amendment to the pending proposal

Not to change its mechanism — that is right — but to correct two fields before it is approved:

1. **Delete or re-base the `task_level_false_failure_rate` prediction.** It is unsupported: the measured
   rate is 0/237, not 6.2 %.
2. **Replace success criterion 2** ("task-level false failure count falls to 0") with something that can
   fail: *"the count of runs whose execution verdict is `failed` while `carry_release_confirmed` is true
   falls to 0 across the 238-run archive."* That criterion is currently 47 and is a real target.

Both are field edits to a JSON proposal, not to a frozen file, and they are **recommendations — the
proposal remains unapproved and I have not modified it.**

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_historical_regrade_20261112/regrade_archives.py
python3 setup/acceptance/evobot_lead_preregistration_test_20261112/test_preregistration.py
```

Offline, no simulator. The second script reads the pending proposal, checks which of its predictions the
archive can test, and reports each as supported / unsupported / untestable rather than assuming.
