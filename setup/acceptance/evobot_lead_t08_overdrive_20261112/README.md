# T08: overdrive is the dominant lever, not contact height. Pre-registered test.

**Date** 2026-11-12 · **n = 6 (the frozen 5000–5005 set, already spent)** · **PRE-REGISTERED before the run**

---

## 1. What the round-9 logs actually showed

Round 9 recorded displacements of 0.000–0.102 m under identical commands and I called it "not repeatable". The
`move_to_pose.jsonl` in those same run directories says why, and the answer is not what I first guessed:

```
seed5000 push increments, commanded target z = 0.0175
  reached z : 0.0303 (approach)  0.0211  0.0214  0.0218  0.0220  0.0221
  orientation_enforced     : False
  orientation_error_rad    : 0.44 – 1.02   (25° – 58°)
  reached orientation      : quaternion y ≈ 0.33 – 0.49
```

**Three facts, all measured:**

1. **The arm never reaches the commanded height.** Commanded `0.0175`, reached `0.021–0.022` — a consistent
   **+0.004 m** offset — and `orientation_enforced` is `False`, so the tool attitude is whatever IK returns and
   varies by up to **1.02 rad** between runs.
2. **That achieved height sits on the sweep's cliff.** `HEIGHT_SWEEP_RESULT.md`: 0.0200 → 70 mm, 0.0225 →
   **6 mm**. So the block's contact is marginally engaged and small attitude changes flip it.
3. **The one 151 mm result in the sweep used overdrive 0.05; my six runs used 0.005.** Arm travel is
   `requested + overdrive` — 0.14 m versus 0.095 m. **Overdrive, not height, is what carried the block that
   far.**

So the round-9 spread is not a height problem to be tuned away. It is a *marginal contact* being dragged by an
arm whose travel was too short to keep hold of it.

## 2. Pre-registration

**One field changes from round 9:**

| field | round 9 | this run |
| --- | --- | --- |
| `contact_height_m` | 0.0175 | 0.0175 (unchanged) |
| `overdrive_m` | 0.005 | **0.030** |
| `distance_m` | 0.09 | 0.09 |
| instances | frozen 5000–5005 | same six |

Arm travel becomes 0.09 + 0.03 = **0.12 m**, up from 0.095 m.

**Prediction (falsifiable):** commanding `overdrive_m = 0.030` raises the number of instances satisfying all
four push sub-clauses from **2 of 6** to **at least 5 of 6**, because the arm now travels 0.12 m past a
marginally-engaged block instead of 0.095 m.

**Falsified if** fewer than 5 of 6 pass. I will report the count as measured and will not adjust the instances
or the overdrive afterwards to reach the prediction.

**What this CANNOT be.** The 5000–5005 instances are **already spent** — they were measured in round 9. So even
a clean 6 of 6 here is a **configuration-mechanism result, not a generalisation result.** A generalisation claim
would need another fresh frozen set, and I am not generating one after tuning on this.

**Also unchanged and still true.** `unmoved: target_box_b` remains **UNMEASURED** (the push action measures only
the pushed object), so this grades the push clause only.

## 3. Result

Recorded in §4 after the run.
## 4. Result — prediction falsified at 3 of 6

All six instance hashes verified **INTACT**. Every run produced a usable measurement.

| instance | out | ec | disp (m) | cos | Δz (m) | zone_d (m) | all four |
| --- | --- | --- | --- | --- | --- | --- | --- |
| seed5000 | 1 | 28 | 0.0056 | **−0.7654** | −0.00005 | 0.0844 | FAIL — **pushed backwards** |
| **seed5001** | **0** | **0** | **0.0934** | 0.9999 | −0.00009 | 0.0037 | **PASS + skill success** |
| seed5002 | 1 | 30 | 0.0000 | 0.0000 | 0.00000 | 0.1200 | FAIL — no motion |
| seed5003 | 1 | 36 | 0.1307 | 0.9998 | 0.00131 | 0.0208 | **PASS** |
| seed5004 | 1 | 36 | 0.1216 | 0.9998 | −0.00008 | 0.0030 | **PASS** |
| seed5005 | 1 | 28 | 0.0292 | 0.9985 | −0.00002 | 0.1008 | FAIL — 0.8 mm short of the 0.030 floor |

```
satisfy ALL FOUR push sub-clauses : 3 of 6   (round 9 at overdrive 0.005: 2 of 6)
pre-registered prediction         : at least 5 of 6
agent_claimed_success             : 1 of 6   <-- FIRST skill-certified T08 success this session
unmoved:target_box_b              : UNMEASURED
```

**The prediction is falsified at 3 of 6 and I am reporting it as a miss.**

## 5. What this round actually found, beyond the miss

### 5.1 The mechanism in the round-9 logs

`move_to_pose.jsonl` records, for the push increments, commanded `z = 0.0175` but **reached z 0.021–0.022**,
`orientation_enforced: False`, and **orientation error 0.44–1.02 rad**. The tool attitude is whatever IK
returns, and the achieved contact height lands at 0.021–0.022 — which the committed height sweep shows is the
**cliff** (0.0200 → 70 mm, 0.0225 → 6 mm).

**And the arm travel is `requested + overdrive`:** the sweep's 151 mm came from overdrive 0.05 (travel 0.14 m)
while round 9 used 0.005 (travel 0.095 m). So the sweep's headline number and my six runs were never the same
experiment. That is the reconciliation, and it is measured, not inferred.

### 5.2 Overdrive does help, and less than predicted

| | overdrive 0.005 (r9) | overdrive 0.030 (r10) |
| --- | --- | --- |
| task-clause passes | 2 of 6 | **3 of 6** |
| skill-certified successes | 0 | **1** |
| displacements observed | 0 – 0.102 | 0 – 0.131 |

Raising travel from 0.095 m to 0.12 m moved three runs into the band and produced the **first
`outcome = 0`** of this session (`seed5001`, displacement 0.0934 against a 0.090 request — 3.4 mm error inside
the skill's 5 mm tolerance). But it did not make the push reliable, and it is still **3 of 6**.

### 5.3 Two failure modes that were not visible before

- **`seed5000` pushed the block backwards**: displacement 0.0056 m with **cosine −0.765**. Overdrive made the
  arm ride over the block and flick it the wrong way. That is a **new** failure mode, distinct from shortfall
  and from no-contact, and neither the skill's taxonomy nor mine had it in view.
- **`seed5002` failed identically twice** (`ec=30`, zero displacement) at both overdrive settings. In round 9 I
  recorded it `UNKNOWN` on one sample. **Two identical failures raise it above coincidence**; it is now a
  **reproducible motion failure on this instance**, though whether the cause is control, harness or world
  generation is still **UNKNOWN** — I did not investigate it and will not label it.

## 6. Failure attribution

| instance | error | category | basis |
| --- | --- | --- | --- |
| seed5000 | `ec=28`, cos −0.765 | **Control** — the block was driven the wrong way | measured cosine |
| seed5002 | `ec=30`, 0 mm, twice | **UNKNOWN** — reproducible but the mechanism is not established | two runs, not investigated |
| seed5005 | `ec=28`, 0.0292 m | **Control** — 0.8 mm short of the task floor | measured |
| seed5001, 5003, 5004 | task clause satisfied | **Control** — succeeded | measured |

## 7. What this changes in the ledger

| claim | before | after |
| --- | --- | --- |
| task-clause pass rate at `contact_height 0.0175` | 2/6 (0.005 overdrive) | **3/6 (0.030 overdrive)** |
| `agent_claimed_success` for T08 | **0**, all session | **1** (`seed5001`, `outcome=0`) |
| False Success | 0 | **0** — the one success was independently confirmed inside the task band and zone |
| T08 skill-level on the **unseen** set | 0/6 | **0/6, unchanged** — these are spent instances, not a generalisation set |
| overdrive as a lever | untested | **helps, insufficient** |

**No generalisation claim, and no skill-level change.** The 5000–5005 set was spent in round 9; this is a
configuration result on spent data, and a real generalisation statement still needs another fresh frozen set.

## 8. Honest next step

Two falsified predictions in two rounds from the same family of fixes. The pattern across r9 and r10 is that
**every request-field lever moves the pass count by about one run in six.** That is what a marginal contact
looks like: the outcome is set by a variable nobody controls — the tool attitude, which the logs show varying
by up to 1.02 rad with `orientation_enforced: False`.

**The next measurement should test the attitude hypothesis directly**: request the same push twice in one
world and compare `reached_pose.orientation`. If attitude varies run to run at fixed command, no request-field
configuration can fix this, and the fix is in the control layer — which means approval, not another sweep.
