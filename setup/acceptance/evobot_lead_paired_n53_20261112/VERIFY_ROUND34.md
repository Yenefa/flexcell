# Round 35: round 34's conclusion needs verification — new evidence both supports and complicates it

**Status: round 34's claim is NOT established.** Downgraded from "CRITICAL: T08 fails on missing evidence" to
"one trial shows a correct push rejected for missing evidence; the general claim is unverified."

---

## 1. What I found, and it cuts both ways

`evaluate.py` is invoked with **exactly two arguments** (`sys.argv[1], sys.argv[2]`, line 361). **There is no
trajectory CLI argument.** Yet T08 verdicts carry `trajectory_required: true`.

The **pilot's own** `verdict_t1.json` — from the arm that produced the claimed 4/5:

```
terminal_passed : False
failed_clauses  : ['push:target_box_a']
displacement_m  : 0.07447
direction_cosine: -0.98753          <-- FAILS the 0.9 minimum
inside_zone     : false  (0.17393 vs radius 0.06)
reason          : "no trajectory for this object: ..."
```

**The pilot's trial 1 failed on real geometry** and carried the same trajectory note. The `reason` field appears
on failures generally — it is **not proof** that missing trajectory was the deciding factor.

## 2. So round 34 over-reached

Round 34 generalised from one trial whose geometry did pass. The reading was reasonable **for that trial**
(`inside_zone: true`, `cosine: 0.99999`) but **not for the clause in general**.

## 3. The unresolved contradiction I must not paper over

| source | says |
| --- | --- |
| pilot `recovery.tsv` | trials 2,3,4,5 `terminal_passed=True` → **4/5** |
| pilot `verdict_t1.json` | `terminal_passed: False` with the trajectory note |
| current run, all 26 | `terminal_passed=False`, every one with the trajectory note |

**Either the pilot's True values were produced under different evidence conditions, or the tsv column is
mislabelled.** Until settled, **no T08 figure in this repository is citable — including the pilot's 4/5 and my
own 0/26.**

## 4. What remains true regardless

- `evaluate.py` has **no trajectory CLI argument** — must be explained before any T08 number is trusted
- the **current** trial 1 achieved `displacement 0.14965, vertical 0.0, cosine 0.99999, inside_zone true` and was
  graded `terminal_passed=False`
- **0/26 graded passes** stand as recorded
- my round-17 claim that the arm "cannot do T08" remains **unsupported**: a correct physical push did occur

## 5. Next step, precisely

Read `evaluate.py`'s push clause and its `passed`/`terminal_passed` separation, then re-grade **one pilot trial**
and **one current trial** from stored artifacts. **That single comparison decides whether this project has a T08
result at all.**
