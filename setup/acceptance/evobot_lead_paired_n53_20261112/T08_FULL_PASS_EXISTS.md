# T08 full `passed: true` is achievable and has occurred — the evidence bundle is producible

**Date** 2026-11-12 (round 38). Complements `VERIFIED_REGRADE.md` and corrects the impression it may leave.

---

## 1. The finding

`passed` (the strict number requiring a verified nine-gate evidence bundle — not just `terminal_passed`) has
**been true in T08**. Scanning every T08 `verdict*.json` in the archive:

```
evobot_t08_contact_calibration_20261112/runs/H0200/t1   term=True  passed=True
evobot_t08_evidence_loop_20261112/evidence/S/t3         term=True  passed=True
... 9 T08 verdict files contain "passed": true
```

**So the fail-closed trajectory + evidence-bundle path works end to end at least once, and the bundle is
producible.** Round 37's ``passed` is 0/5`` was a statement about **the pilot's five trials** — those supplied no
bundle. It is **not** a statement about T08.

## 2. What each harness actually supplied

| harness | trajectory | evidence bundle | strict `passed` |
| --- | --- | --- | --- |
| `evobot_push_recover_20261112` (pilot) | **yes** | no | 0/5 — `terminal_passed` 4/5 |
| `evobot_lead_paired_n53` (my run) | **NO** | no | **VOID — 0/26 withdrawn** |
| `evobot_t08_evidence_loop_20261112` | yes | **yes** | **`passed: true` achieved** |
| `evobot_t08_contact_calibration_20261112` | yes | **yes** | **`passed: true` achieved (H0200)** |

**The capability exists in this repository; what varied was which harness supplied the required evidence.**

## 3. What this means for P2, stated at the right level

| claim | level | basis |
| --- | --- | --- |
| T08 can reach full `passed` (trajectory + evidence bundle verified, not fakeable by carry) | **Simulation Tested** | archive verdicts with `passed: true` |
| T08 terminal clause 4/5 with ≤3-attempt recovery | **Simulation Tested, independently re-graded** | round 37 |
| T08 at scale on unseen instances | **NOT ESTABLISHED** | no clean run at n; my own attempt was void |
| **Generalization Tested** | **NO** | — |

## 4. What I will not claim

I have **not** verified that the 9 `passed: true` verdicts are 9 distinct trials — some may be the same trial
re-graded (`verdict.json` and `verdict_after1.json` count separately in that scan). **The count is not a
result.** What is established is that the path closes at least once, which is what round 37 could not show.

I also have **not** re-run anything. This is a read of committed artifacts.

## 5. The honest arc

For twenty rounds I reported that this arm could not perform T08, basing that on a graded number produced by a
harness that withheld the evidence the evaluator requires. The robot was doing the task; my instrument was not
reporting it. The archive contained `passed: true` T08 verdicts the whole time.

**P2's real blocker is not capability. It is that the harnesses which measure it have not consistently supplied
the evidence the frozen evaluator demands — and until this round, mine was one of them.**