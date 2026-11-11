# P3's improvement chain is not gated — and the freeze has three generations, so its own verifier can never pass

**Date** 2026-11-12 · **Method** offline: run the loop end to end, then test the gate it claims to use
**Status: three confirmed defects in the P3 improvement event chain. No pinned file edited.**

---

## 0. A correction I made to my own first draft

My first draft of this document said the frozen contract had drifted five times and the freeze's rule was
violated. **That was too strong and I checked it before publishing.** The project has a **formal re-pin
process** (`setup/acceptance/evobot_freeze_change_20261111/`, commit `102d0df5`: *"formal pinned-file change,
grading proven identical"*). There are **three successive baselines**, each a legitimate re-pin:

| generation | pinned files drifted **now** |
| --- | --- |
| `evobot_capability_freeze_20261111/capability_baseline.json` (oldest) | **4** |
| `evobot_freeze_change_20261111/capability_baseline.json` | **3** |
| `benchmark/capability_baseline.json` (**live**) | **1** |

So the freeze was maintained, not abandoned. The real defects are narrower, and one of them is sharper
than the original claim.

## 1. What I set out to do

Rounds 3 and 4 were measurement discipline. This round is meant to be P3 capability work, so I ran the
improvement event chain end to end and asked whether it improves anything:

```bash
python3 evolution/proposals/run_loop.py
```

Its docstring: *"This is the loop end to end: measured failures -> clustered signature -> proposal ->
**existing regression gate.**"*

It ran, it produced proposals, and **it is not gated.**

## 2. Defect 1 — the regression gate is explicitly disabled

`evolution/proposals/run_loop.py:68`:

```python
ok, reason = regress.gate(proposal, run_regressions=False)   # and gate's default is True
```

`regress.gate`'s docstring: *"This is the guard that makes Baseline C different from \"let the agent edit
code\": the agent may propose, but the gate decides, using independent verifiers."* The caller asks it not
to decide.

Skipping the regressions reduces the gate to four structural checks plus the held-out baseline. **A
proposal that breaks every verifier in the repository is accepted**, printed as `ACCEPTED`, and written.

## 3. Defect 2 — why it was disabled, and the reason is real

I enabled it and ran it properly. **105 of 109 verifiers pass; 4 fail for reasons unrelated to any
proposal:**

| verifier | reported failure |
| --- | --- |
| `evobot_baseline_a_v0_20261111` | 1 failed |
| `evobot_capability_freeze_20261111` | `AssertionError: ['pinned file CHANGED: benchmark/evaluators/evaluate.py']` |
| `evobot_p2_feasibility_20261111` | 23/26 claims hold |
| `evobot_t08_push_criterion_20261111` | 7 passed, 2 failed |

**Enabling the gate would therefore reject every proposal forever, for pre-existing reasons.** Someone
turned it off rather than distinguishing *this proposal caused a failure* from *this verifier was already
failing*. That is how a gate dies, and it is what happened: **the gate has never gated anything.**

## 4. Defect 3 — the freeze verifier validates a superseded baseline, so it can never pass again

One of the four failing verifiers is `evobot_capability_freeze_20261111`. It is not noise, and it is not a
real regression either. It checks the **oldest** baseline, which was legitimately superseded twice.

Its four drifts are all accounted for by the two later re-pins — **except that the verifier was never
retired or redirected at the live baseline.** So it fails permanently on files that are supposed to have
changed, and it contributes one of the four reasons the improvement gate stays off.

**The live baseline has exactly one drift:**

```
benchmark/capability_baseline.json  ->  pinned=9  drifted=1
  DRIFT  benchmark/evaluators/evaluate.py
```

`evaluate.py` last changed at `4fd36cd6` (2026-11-12), *"fix(t08): the evidence verifier rejected every valid
push because evaluate.py never passed limits"* — a semantic change to grading, made after the live baseline
was recorded, and **the live baseline was not updated to match.**

So the sharp, defensible claim is: **the live pinned contract records a hash for `evaluate.py` that the file
no longer has, and the acceptance verifier checks a two-generations-old baseline instead of the live one.**

## 5. The stale record

```
setup/acceptance/evobot_capability_freeze_20261111/freeze_check.txt
  {"baseline": "INTACT", "pinned": 9}

setup/acceptance/evobot_capability_freeze_20261111/evidence_summary.txt
  verifier failures: 0
```

**Both are stale.** The verifier currently fails, and the summary says zero failures. Anyone reading that
directory concludes the baseline holds.

Same pathology as round 3's `released: false` beside `carry_release_confirmed: true`: **a record asserting a
fact the repository contradicts.**

## 6. What this means for the project's numbers

| claim | status |
| --- | --- |
| the contract defining correctness has been maintained with formal re-pins | **YES** — three generations, process exists |
| the **live** baseline matches the code | **NO** — `evaluate.py` drifted, unrecorded |
| the freeze verifier proves the freeze holds | **NO** — it validates a superseded baseline and always fails |
| the regression gate blocks bad proposals | **NO** — called with `run_regressions=False` |
| `freeze_check.txt` / `evidence_summary.txt` are true | **NO** — both stale |

**I am not claiming any archived number is wrong.** The re-pins were formal, and one explicitly states
"grading proven identical". What is missing is that **the live baseline no longer describes the code**, so
the one document that could certify comparability cannot.

## 7. What I did not do

- **No pinned file edited.** All nine, in every generation, untouched.
- **No re-run performed.** Re-running 17 batches is a sanctioned-cost operation and a human decision.
- I reverted one accidental side effect: running the loop rewrote `evolution/proposals/actuator_stall.json`;
  I restored it with `git checkout`. **The loop overwrites proposals in place**, which is itself worth
  noting — a proposal awaiting review can be silently replaced by a regeneration.

## 8. Recommended actions (human decision)

1. **Update the live baseline** (`benchmark/capability_baseline.json`) for `evaluate.py`, with the same
   "grading proven identical" evidence the previous re-pin produced — or, if grading did change, record
   which archived numbers predate it.
2. **Retire or redirect `evobot_capability_freeze_20261111/verify.py`** at the live baseline. A verifier that
   can never pass is worse than none: it disables the gate for everyone.
3. **Regenerate `freeze_check.txt` from the verifier**, never by hand.
4. **Replace the skipped gate with a differential one** — no *new* verifier failures versus a recorded
   baseline, rather than all 109 green. That is the only form that can be on given four pre-existing
   failures, and it is what makes the guard real again.
5. **Stop overwriting proposal files** in `run_loop.py`.

## 9. Reproduce

```bash
python3 setup/acceptance/evobot_lead_p3_gate_integrity_20261112/check_gate_integrity.py
```

Offline. Prints the gate call site, runs all 109 verifiers, and compares **every generation** of the pinned
baseline against the actual files, so the live generation is distinguishable from the superseded ones.
