# Correction: the 11 disagreements are NOT my criterion being loose - every sub-condition passes

Round 84 withdrew an 18/18 claim on the grounds that my hand scoring disagreed with the evaluator
on 11 of 18 runs, and guessed the cause was a clause I was not checking. **That guess was wrong.**

## What the evaluator's own evidence says for those 11 runs

| run | displacement | cosine | inside_zone | zone distance | reason |
| --- | --- | --- | --- | --- | --- |
| fix_2000_0.08_1 | 0.13089 | 0.99987 | **True** | 0.03094 | **None** |
| fix_2000_0.08_2 | 0.12270 | 0.99961 | **True** | 0.02291 | **None** |
| fix_2000_0.08_3 | 0.12960 | 0.99941 | **True** | 0.02986 | **None** |
| fix_2000_0.0_3 | 0.11261 | 0.99969 | **True** | 0.01289 | **None** |
| fix_3001_0.08_1 | 0.10734 | 0.98329 | **True** | 0.02031 | **None** |
| fix_3001_0.08_2 | 0.13332 | 0.99826 | **True** | 0.03401 | **None** |
| fix_3001_0.08_3 | 0.11747 | 0.99746 | **True** | 0.01910 | **None** |
| fix_3001_0.0_1 | 0.11825 | 0.99731 | **True** | 0.01992 | **None** |
| fix_3001_0.0_2 | 0.12936 | 0.99622 | **True** | 0.03098 | **None** |
| fix_3001_0.0_3 | 0.12765 | 0.99818 | **True** | 0.02848 | **None** |

Against the task's own limits - displacement 0.03 to 0.15, cosine at least 0.9, vertical at most
0.02, zone radius 0.06 - **every one of these runs satisfies every stated condition**, and the
clause's own `evidence` dictionary records that: `inside_zone: True`, `reason: None`.

**And the clause reports `ok: False`.**

## So where does the disagreement actually lie

Not in my hand scoring. I computed zone distance from the box's final position and the zone
centre; the evaluator computed the same thing and got 0.0129 to 0.0340, agreeing with me to four
decimals.

**The disagreement is between the evaluator's own evidence and the evaluator's own verdict.**

Possible explanations, none established:

- a condition inside `push` that is checked but not recorded in `evidence`
- a value taken from a different part of the bundle than the one reported
- a defect in the clause

**I am not going to assert the last one without reading the clause body.** That is the next step.

## What this does to the round-84 withdrawal

The **18/18 figure stays withdrawn** - it was my criterion and I should not have reported it as a
result. But the *reason* I gave was wrong: I implied my scoring was too loose and the evaluator
was catching something I missed. **The evaluator's own evidence says otherwise.**

## What is solid right now

- **7 of 18** runs pass every clause and are then rejected by `gripper`.
- **11 of 18** have a `push` clause whose evidence satisfies every stated limit while the clause
  reports failure.
- Staging reports SUCCEEDED 18/18 where it was 0 before the fix; that mechanism is established.
- **0 of 18 verified.** T08 remains `CALIBRATION_UNSUPPORTED`.