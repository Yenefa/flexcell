# The pending fix's safety argument does not hold as written — it is safe for an unrelated reason

**Date** 2026-11-12 · **Subject** `evolution/proposals/release_confirmation_preregistration.json` (unapproved)
**Status: the proposal's mechanism is right; its stated safety argument is incomplete. Nothing modified.**

---

## 1. The claim I tested

The proposal replaces the `place` release predicate (gripper aperture → carry confirmation) and justifies
its safety with:

> *"The evaluator grades the world, not the skill's self-report. Reclassifying the self-report cannot make
> a failing world pass; it can only stop a succeeding world from being called a failure."*

That is exactly the kind of argument this project has learned to distrust — it asserts that a field is
off the grading path without checking. So I checked.

## 2. It is false as written

`benchmark/evaluators/observe_from_run.py`, lines **74** and **114** — the module that *builds the
observation the evaluator then grades*:

```python
# line 74
if name and pose and row.get("released", True):
    provenance[name] = "place.box_after"

# line 114
if not name or not pose or not row.get("released", True):
    continue
```

**`place.released` is read on the grading path.** Flipping it does not merely reclassify a self-report —
it changes which pose the observation builder accepts. The proposal's safety argument is therefore **not
established by its own reasoning.**

## 3. Why it is safe anyway — and the reason is incidental

Measured across every archived `place.jsonl`:

```
place rows with released=False            :  51
  ...that carry box_after                 :   0   <-- the decisive number
place rows with released=True AND box_after: 488
```

`observe_from_run` only uses `place.box_after` when the row has **both** a pose and a truthy `released`.
On all 51 denied rows `box_after` is **absent**, so `pose` is `None` and the row is skipped **either way**.
Flipping `released` alone changes nothing.

**But that safety comes from the failure path not writing `box_after` — an incidental property of the
current code, not a guarantee.** If someone later fixes that omission for unrelated reasons, the safety
evaporates silently.

## 4. The proposal's own prediction is the risky part

The proposal predicts:

```
"place_box_after_will_be_recorded": true
```

**That is a second, distinct change, and it is the one that touches the evaluator.** If `box_after` starts
being recorded on the failure path, then for all 51 rows `observe_from_run` would begin using
`place.box_after` as the object pose instead of falling back to `verify.jsonl`.

| part | change | grading input | risk |
| --- | --- | --- | --- |
| **1** | flip `released` to the carry confirmation | **unchanged** | none — but only because `box_after` is absent |
| **2** | start recording `box_after` | **changed for 51 rows** | not covered by the proposal's safety argument |

The proposal bundles both parts under a single safety argument that only covers the first.

## 5. Would part 2 create false success? Not demonstrated either way

I cannot answer this offline, and I am not going to assert it. `box_after` does not exist on these rows,
so its future value cannot be read from the archive — it would be whatever the patched skill measures at
release time.

What I can say: for the **11 runs whose object never left its start pose**, that pose is not in the
destination, so a false success is *unlikely*. **Unlikely is not a test.** Part 2 needs its own
regression check on a real run after approval.

## 6. Recommended amendment before approval

In addition to the amendments in `evobot_lead_preregistration_test_20261112/` (re-base the task-level
prediction, replace the vacuous success criterion), add one:

3. **Split the proposal into part 1 and part 2 with separate success criteria.** Part 1 (flip the
   predicate) is verifiable by `skill_layer_release_failures: 47 → 0` and cannot move the grading input.
   Part 2 (record `box_after`) changes the observation for 51 rows and needs a paired run showing the
   final pass count does not fall **and** the `provenance` shift does not alter any verdict.

And correct the anti-gaming rationale itself, which is currently wrong: it should say the field **is**
read by `observe_from_run`, that part 1 is therefore only conditionally safe, and name the condition.

**Nothing has been modified.** The proposal remains `approved: false`, `place_server.py` is untouched.

## 7. This is the third time the same lesson has appeared

| where | the assumption | the check that broke it |
| --- | --- | --- |
| round 2, T08 gate | aperture travel means a grasp | 0.42 mm separation from air |
| round 3, `place` | aperture means a release | `carry_release_confirmed: true` in the same record |
| **round 4, this proposal** | **"the evaluator doesn't read it"** | **`observe_from_run.py:74` reads it** |

Same shape every time: **a claim that some quantity is not used, made without tracing its use.** The
cheap check is a grep; the expensive mistake is publishing the claim first.

## 8. Reproduce

```bash
python3 setup/acceptance/evobot_lead_fix_prefix_validation_20261112/validate_fix_prefix.py
```

Offline, no simulator, no frozen file touched. It greps the observation builder for the coupling, then
measures `box_after` presence on every denied row.
