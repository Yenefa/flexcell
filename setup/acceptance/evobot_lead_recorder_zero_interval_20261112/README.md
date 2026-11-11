# Recorder defect: a single-step contact destroys an otherwise valid evidence bundle

**Date** 2026-11-12 · **Found by** the simulation lane during arm R · **Reproduced and root-caused by the Lead**
**Severity** high — silent, and it invalidates **all nine** gates rather than one

---

## 1. The defect

`recorder.contact_intervals()` opens an interval and sets `end_sim_ns` to the **first touching step**.
When contact is observed for exactly **one** physics step (5 ms), the interval closes with
`start == end`, i.e. a **zero-length** interval. `schema.py` then rejects it:

```
contacts.intervals[6]: empty or inverted interval
```

One malformed interval in the `contacts` section makes `schema.validate()` return a problem, which
makes the bundle invalid, which turns **every** gate into "not evaluable" — not just the contact gate.

## 2. Reproduction (Lead, on the sim lane's own artifact)

```
R/t4 evidence_bundle.json -> contacts.intervals : 14 intervals
  [5] start=13250000000 end=13280000000 span=   30000000 ns   (30 ms)
  [6] start=13290000000 end=13290000000 span=          0 ns   <== ZERO LENGTH
  [7] start=13305000000 end=13495000000 span=  190000000 ns
schema.validate(bundle) -> 1 problem: contacts.intervals[6]: empty or inverted interval

R/t4 trial_record.json:
  terminal_passed=false  passed=false  evidence_status=INCOMPLETE_OR_INVALID_EVIDENCE
  failed_gates = [terminal, trajectory, table_support, protected_unmoved, no_lift,
                  pusher_contact, gripper, no_attachment, no_teleport]   <- ALL NINE
```

**The all-nine failure is the tell.** A physical condition that affects contact cannot legitimately fail
`no_teleport` or `protected_unmoved`. When every gate fails at once, the bundle is invalid, not the run.

## 3. Why this is dangerous rather than merely untidy

On R/t4 nothing is hidden: the trial was already failing on direction (cos −0.99897). But the defect is
**silent and outcome-independent**. On a **clean** trial — correct displacement, correct direction, no
lift — a single 5 ms contact would:

1. produce a zero-length interval,
2. fail schema validation,
3. turn all nine gates into "not evaluable",
4. yield `passed=false` with `evidence_status=INCOMPLETE_OR_INVALID_EVIDENCE`.

The trial would be recorded as a **failure of the robot** when in fact the **recorder** discarded the
evidence. That is precisely the misclassification the mission forbids: *"证据不足，不等于已经证明机器人
操作失败"* — insufficient evidence must never be written down as a confirmed physical failure.

It also means the failure is **probabilistic**: whether it strikes depends on whether any contact
happens to last exactly one step, which varies with contact geometry and timing. A batch could be
clean for twenty runs and then lose one for no visible reason.

## 4. Root cause, precisely

| Layer | Behaviour | Correct? |
| --- | --- | --- |
| `recorder.contact_intervals()` | sets `end_sim_ns` = first touching step; a one-step contact therefore closes at its own start | **NO** — should close at `start + step_duration`, or emit the interval as `[start, start+dt)` |
| `schema.py` | rejects `start >= end` as "empty or inverted" | **YES** — a zero-length interval is genuinely malformed and must not be silently accepted |
| `verify.py` | every gate returns not-evaluable on a schema problem | **YES** — fail-closed is the designed behaviour |
| the batch driver | reports all-nine-failed as a normal trial outcome | **NO** — should surface `INVALID_EVIDENCE` distinctly (the sim lane did label it, to their credit) |

**The bug is in the recorder, not in the validator.** The validator caught a real malformation; the
recorder produced it. The fix is one line in `contact_intervals()` — but `recorder.py` is a frozen
file this round, so it is **reported, not patched**.

## 5. Why the sim lane's handling was correct

They kept the bundle **verbatim** and did not hand-patch the JSON. Editing an evidence artifact to make
it validate would have destroyed the only record of the defect and manufactured a pass from a
corrupted bundle. They labelled the trial `INCOMPLETE_OR_INVALID_EVIDENCE` rather than a robot failure.
That is the right call and it is recorded here as such.

## 6. Disposition

| Item | Decision |
| --- | --- |
| Patch `recorder.py` this round | **NO** — frozen file; needs approval and a version bump |
| Re-run R/t4 | **NO** — it failed on direction independently; the defect hid nothing here |
| R/t4's verdict | **INVALID_INFRA**, not a robot failure — recorded as such |
| Effect on arm R's statistics | R/t4 **excluded from the pass-rate denominator** as an invalid measurement, and the exclusion is stated rather than silently dropped |

**Required before any future batch is trusted:** a recorder regression test that feeds a one-step contact
and asserts the emitted interval is non-empty. Such a test does not exist today — the 75-test suite
passes while this defect is live, which is itself worth noting.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_recorder_zero_interval_20261112/check_zero_interval.py
```

Reads `R/t4/evidence_bundle.json` and runs the real `schema.validate()`. No simulator, no model calls.
