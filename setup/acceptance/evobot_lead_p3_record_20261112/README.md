# P3 experience record — one candidate seed (NOT appended)

**Date** 2026-11-12 · **Lane** exec-mystery · request: author ONE review-grade experience record
**Status** seed written and dry-run ACCEPTed. **`records.jsonl` was NOT touched** (append is the Lead's decision).

---

## 1. Deliverable

```
setup/acceptance/evobot_lead_p3_record_20261112/
  seed_margin_consumed.json    <- the seed (one record); pass to --seeds
  _selfcheck.py                <- reproducible re-verification + tamper tests
  README.md                    <- this note
```

Dry-run command actually run (WSL, from repo root):

```bash
python3 evolution/experience/seed_from_evidence.py --dry-run \
  --seeds setup/acceptance/evobot_lead_p3_record_20261112/seed_margin_consumed.json
```

Exact stdout:

```
ACCEPT T13-recover-clearance-margin provenance + actionability ok

accepted: 1   rejected: 0   (dry_run=True)
nothing written - dry run
```

Exit code 0.

---

## 2. The record

| field | value |
| --- | --- |
| `task_id` | `T13-recover-clearance-margin` |
| `failure_class` | **`control`** (allowed string, used as-is from `store.FAILURE_CLASSES`) |
| `source_run` | `setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68` |
| `outcome` | `failed` |
| `provenance_verified` | `True` (set by the seeder after the check ran) |
| `validated` | `False` — correctly left for a second party |
| `record_sha256` | `688f0862066d582e180268c48fd58fe44adf752bdf06a1b3a91c6a7dfb3daf9f` |

`evidence` (every value matched a **typed JSON field** in a machine-readable file under
`source_run`; resolved files listed in `evidence_files`):

```json
{"clearance_m": 0.05,
 "place_error_m": 0.009658022849775898,
 "final_position_error_m": 0.009651925313011562}
```

`lesson` (221 chars, the reviewer's control fact — not a planning strategy):

> Two destinations 56 mm apart left only 6 mm over the 50 mm clearance; one object settled
> 9.65 mm off its commanded point, inside the 20 mm accepted limit, leaving the next
> destination 1.4 mm short and refused as occupied.

---

## 3. Every number re-derived from the cited run (not copied from the prompt)

From `plan.json` (`stages[].place_pose`, `position_tolerance_m`, `clearance_m`) and
`sim/skills/place.jsonl` (`box_after`):

| quantity | value | source |
| --- | --- | --- |
| commanded separation between the two destinations | **56.000 mm** | `plan.json` `stages[0/1].place_pose` `[0.092,-0.15]` vs `[0.148,-0.15]` |
| accepted error limit | **20.0 mm** | `plan.json` `position_tolerance_m = 0.02` |
| measured error of the first object | **9.652 mm** | `place.jsonl` `box_after` vs commanded pose |
| nominal margin over clearance | **+6.000 mm** | 56 − 50 |
| margin left after the error | **−1.401 mm** (shortfall) | measured separation 48.599 mm − 50 mm |
| clearance | **50.0 mm** | `plan.json` `clearance_m = 0.05` |

This reproduces the reviewer's verbatim finding exactly: *"with a ±28 mm spread, a 9.65 mm
placement error leaves 1.4 mm against a 50 mm clearance"*. The ±28 mm spread is real
(`stages[].spread_offset_m = ∓0.028`) and is what makes the nominal margin only 6 mm.

---

## 4. Why the lesson is `control` and not `planning`

The plan was **correct**: it chose a free destination per object and the first placement
succeeded (`place.jsonl` `outcome=0`, `released=true`, `place_error_m≈9.66 mm` inside the
accepted limit). The failure (error 61, "state drift or occupied destination before
target_box_b-1") happened because a **within-limit actuator error consumed a geometric
budget** that had only 6 mm of slack. That is a control-budget fact, not a planning choice.
No claim is made about what the planner should have done.

---

## 5. Honest limitations — facts requested that I could NOT put in `evidence`

These are verified problems, not preferences. Each was tested, not assumed.

**(a) The 20 mm accepted limit cannot be an evidence fact.** The only machine-readable
field carrying it is `position_tolerance_m` (`plan.json`, `plan_retry.json`,
`move_to_pose.jsonl` — full value scan found no other field equal to `0.02`). But
`store.FORBIDDEN_TOPICS` contains `"tolerance"` and `_check_scope` runs over
`json.dumps(evidence)`, so citing it is refused:

```
add position_tolerance_m 0.02 -> REJECT  STORE REFUSED: experience record touches a protected topic: tolerance
```

It therefore appears **only in the lesson prose**. I verified it directly from
`plan.json`, but a reviewer cannot re-verify it through the evidence dict. **This is a
genuine conflict between "put the tolerance in evidence" and the store's scope guard** —
flagged for the Lead; I did not weaken either side.

**(b) The 1.4 mm margin is derived, not measured.** `grep -c margin` over every `.json` and
`.jsonl` in the run returns **0**. Inventing `margin_m: 0.0014` is refused by design:

```
invented margin_m 0.0014 -> REJECT  PROVENANCE: evidence not found ... : margin_m
```

It lives in the lesson and is re-derived in §3 above.

**(c) `error_code` was REMOVED from evidence deliberately.** The run contains **both**
`error_code: 61` (original, `failure_evidence.json`) and `error_code: 60` (retry,
`sim/skills/composites/composite-34f3ca6017de4390.jsonl`). A tamper test proved the
provenance check cannot tell them apart — changing 61 → 60 still **ACCEPTed**. So the field
is ambiguous within this run and I excluded it rather than ship a fact that is only
accidentally right.

**(d) `spread_offset_m` cannot be cited either** — it is nested inside
`plan.stages[]`, and `verify_provenance._json_objects` only inspects the **top-level**
dict of a `.json` file. It survives only in the lesson prose.

---

## 6. Tamper tests — proof the ACCEPT is live, not vacuous

`_selfcheck.py` mutates the seed and re-reviews it. Results:

| mutation | result |
| --- | --- |
| `clearance_m` 0.05 → 0.06 | **REJECT** provenance |
| `place_error_m` 9.658 → 10.658 mm | **REJECT** provenance |
| `final_position_error_m` → 0.0 | **REJECT** provenance |
| invented `margin_m` 0.0014 | **REJECT** provenance |
| banned `position_tolerance_m` | **REJECT** store scope |
| lesson → landing-spot wording | **REJECT** actionability (`DOWNSTREAM_CODE`) |
| **lesson → planning strategy** | **ACCEPT** ← see §7 |

---

## 7. WARNING for the Lead: the gate does not check truth

A lesson rewritten as a **planning strategy** — *"Choose a free destination for each object
before sending the second one, and order the moves so a later stage is not blocked by an
earlier one."* — passes both gates (**ACCEPT**).

That is, character for character, the shape of the two **REJECTED** records. `check_actionability`
only routes on vocabulary (`DOWNSTREAM` / `HARNESS` / `object|unmoved|zone|order`); it has no
access to what actually happened, so it cannot distinguish a true control fact from a
plausible planning inference. **ACCEPT is necessary, not sufficient.**

The reason this record's lesson is true is not that the gate passed — it is that the lesson
is the independent reviewer's finding and every number in it was re-derived from the cited
artifacts in §3. If the Lead wants a mechanical guard against the round-14 failure mode, it
would have to compare the lesson against the recorded failure mechanism, which no current
checker does.

---

## 8. Scope compliance

- `records.jsonl` untouched (still 6 records); nothing appended.
- `store.py`, `verify_provenance.py`, `seed_from_evidence.py`, `audit_actionability.py` untouched.
- No simulator, no model calls, no commit.
- Wrote only inside `setup/acceptance/evobot_lead_p3_record_20261112/`.
