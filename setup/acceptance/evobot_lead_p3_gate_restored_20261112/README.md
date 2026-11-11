# Restoring P3's gate: reject NEW verifier failures instead of requiring none

**Date** 2026-11-12 · **Status: implemented, unit tested (7/7), and run end to end. `regress.py` untouched (pinned).**
**Evidence level: Designed → Implemented → Unit Tested. NOT Simulation Tested, NOT Independently Verified.**

---

## 1. The problem, in one paragraph

`evolution/proposals/run_loop.py` generated proposals and called `regress.gate(proposal, run_regressions=False)`,
so the independent-verifier regression — the guard its own docstring calls *"the guard that makes Baseline C
different from 'let the agent edit code'"* — never ran. Round 5 established why: four of 109 verifiers fail for
reasons unrelated to any proposal, so an all-green gate rejects everything forever. **The gate was disabled
rather than made differential, and so it has never gated anything.** That is the difference between P3
existing on paper and P3 existing.

## 2. What I built

| file | role | pinned? |
| --- | --- | --- |
| `evolution/validation/known_failures.json` | the four pre-existing failures, each classified with a reason | new |
| `evolution/validation/gate_differential.py` | the gate: structural checks + **no new failures** + side-effect restore | new |
| `evolution/validation/test_gate_differential.py` | seven tests of the logic | new |
| `evolution/proposals/run_loop.py` | **edited**: now calls `gate_differential.gate(proposal)` | not pinned |

`evolution/validation/regress.py` is **pinned and untouched** — the new gate imports it read-only and delegates
its structural checks (`regress.gate(proposal, run_regressions=False)`) rather than duplicating them.

## 3. The rule the gate enforces

```
baselined failure, still failing   -> ACCEPT  (unchanged)
baselined failure, now passing     -> ACCEPT  and report it as an improvement
failure NOT in the baseline        -> REJECT  <-- this is the guard
known_failures.json missing        -> REJECT  (a missing baseline must not be a free pass)
no verifiers found                 -> REJECT  (never accept untested)
```

```
test                                                 result
------------------------------------------------------------------------------
baselined failure unchanged -> ACCEPT                PASS
new failure -> REJECT                                PASS
baselined verifier now clears -> ACCEPT + noted      PASS
missing baseline -> REJECT (fail closed)             PASS
protected path -> REJECT                             PASS
no verifiers -> REJECT                               PASS
verifier side effect -> file restored                PASS

7/7 tests passed   (17.9 s)
```

## 4. Two implementation defects I hit, both worth recording

### 4.1 My first test was wrong, not the gate

I baselined a verifier, ran a **different** verifier, and expected a "cleared" note. A baselined failure can
only be reported cleared if it was actually run. **I fixed the test, not the gate.**

### 4.2 My first side-effect fix used git — and git does not work here

**108 of the 109 `verify.py` write their own `verify_result.json`,** so running the gate mutates the archive it
checks. My first implementation snapshotted via `git status` and restored via `git checkout`.

**Git cannot run in this worktree under WSL.** Its `.git` file holds a Windows absolute path:

```
fatal: not a git repository: .../wt-comp/C:/Users/fuker/.../code_worktrees/wt-comp
```

So both helpers raised, `_dirty_paths()` returned an empty set, and **the restore silently did nothing while
the gate reported success.** I only caught it because the file was still dirty after a full loop run —
the same failure mode this project keeps finding, where a component reports a result it did not achieve.

**Fix: byte snapshots, no git.** Snapshot the files beside each `verify.py`, then write back any whose bytes
changed. Verified in the real environment:

```
verify_result.json sha before : d1ef15f46b50a2e3
verify_result.json sha after  : d1ef15f46b50a2e3
RESTORED EXACTLY             : True
reason: structure ok; 1 verifier(s) run; 1 known failure(s) unchanged; 0 new
        [restored 1 archive file(s) the verifier run rewrote]
```

### 4.3 And my first snapshot was too wide

A recursive walk of `setup/acceptance/` includes every archived `runs/` subtree — thousands of files the
verifiers cannot touch. Six tests took **over two minutes** and timed out. Scoping the snapshot to one level
inside each directory that holds a `verify.py` brings the suite to **17.9 s**.

## 5. The baseline is honest about what it does not know

| verifier | classification |
| --- | --- |
| `evobot_capability_freeze_20261111` | **STALE_RECORD** — validates the oldest of three superseded baselines, never retired |
| `evobot_p2_feasibility_20261111` | **STALE_PREMISE** — fails because a later commit *added* the push clause it said was missing |
| `evobot_baseline_a_v0_20261111` | **UNKNOWN** — not investigated. Recorded so the gate can run, **not** shown harmless |
| `evobot_t08_push_criterion_20261111` | **UNKNOWN** — same caveat |

The file says plainly that editing it to make a proposal pass is the abuse it exists to prevent. Two entries
are `UNKNOWN` on purpose: **baselining a failure is not a claim that it is benign**, only that it cannot be
attributed to a proposal. Saying otherwise would be the seventh recorded instance of substituting a label for
a cause.

## 6. End-to-end result

See §8 for the run. Before this change the loop's output read:

```
GATE  actuator_stall  n=50  ACCEPTED
       structure accepted (regressions skipped by caller)
```

After:

```
GATE  actuator_stall  n=50  ACCEPTED
       structure ok; 109 verifier(s) run; 4 known failure(s) unchanged; 0 new
```

The difference is five minutes of independent verification per proposal where there was previously none.

## 7. What this does and does not achieve

| claim | status |
| --- | --- |
| the improvement chain now runs a real regression gate | **YES** |
| the gate rejects a proposal that introduces a new failure | **YES, unit tested** |
| the gate restores archive files its own run modifies | **YES, verified byte-identical** |
| the four baselined failures are understood | **NO — two are `UNKNOWN`** |
| P3 / Baseline C is complete | **NO.** This restores the guard. Applying a change still needs human approval, and the seven-field experience records with independent review are a separate, still-missing deliverable |

## 8. Reproduce

```bash
python3 evolution/validation/test_gate_differential.py     # 7/7, ~18 s
python3 evolution/proposals/run_loop.py                    # full chain, ~10 min
```
---

## 9. End-to-end run with the gate ON

```
$ python3 evolution/proposals/run_loop.py
measured failures across all archives: 101
  GATE  actuator_stall         n=50  ACCEPTED
         structure ok; 109 verifier(s) run; 4 known failure(s) unchanged; 0 new
         [restored 1 archive file(s) the verifier run rewrote]
         wrote evolution/proposals/actuator_stall.json
  SKIP  unconfirmed            n=46  no evidence-backed change for unconfirmed yet
  GATE  occupied_destination   n=5   ACCEPTED
         structure ok; 109 verifier(s) run; 4 known failure(s) unchanged; 0 new
         [restored 1 archive file(s) the verifier run rewrote]
         wrote evolution/proposals/occupied_destination.json

proposals written: 2
```

Before this change the same lines read `structure accepted (regressions skipped by caller), id=…`.
**The difference is 109 independent verifications per proposal where there were none.**

Working tree after the full run: **zero `verify_result.json` files dirty.** The restore held across both gate
calls, in the real environment, not only in the unit test.

## 10. What is still missing from P3

Being precise about what this does not do, because the round would otherwise look like more than it is:

| P3 requirement | status |
| --- | --- |
| measured failure → clustered signature → proposal | **working** |
| a proposal is gated by independent verifiers | **working, as of this change** |
| applying a change | **not automatic** — needs human approval for pinned files |
| **seven-field experience records** | **not delivered this round** |
| **independent review of those records** | **not delivered** |
| Baseline C end-to-end improvement event | **not achieved** — no change has yet been applied and re-measured |

So P3's *guard* is restored. P3's *event chain* — the part where an improvement is actually applied and
independently shown to help — still has not happened, and no round so far has done it.
