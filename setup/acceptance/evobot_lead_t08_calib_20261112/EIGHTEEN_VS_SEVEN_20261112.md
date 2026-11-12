# Hand-scored 18/18 vs frozen evaluator 0/18: my criterion was not the evaluator's

All eighteen post-fix runs, scored by hand as "zone distance under 0.06", then run through
`evaluate.py` 0.5.0 with the full evidence chain.

## Results

| | count |
| --- | --- |
| my criterion (zone distance <= 0.06) | **18 / 18** |
| evaluator `terminal_passed` | **7 / 18** |
| evaluator `passed` | **0 / 18** |

Seven runs pass every task clause. **All seven are then rejected by `gripper`.**

Eleven runs fail `terminal` as well - so their clauses did not pass in the evaluator's reading,
even though my hand computation put them inside the zone.

## The two things this establishes

**First: the gripper gate blocks every single run that satisfies the task.** 7 of 7,
unanimously, on four seeds. Round 83 reported one held-out instance of this; it is actually the
complete set.

**Second, and this is the one that matters more: my hand scoring disagrees with the evaluator on
11 of 18 runs.** I reported 18/18 in rounds 81 and 82. The evaluator says 7.

My check was: distance from the box's final position to the zone centre, compared against the
zone radius. The evaluator checks that plus `unmoved:target_box_b`, plus a distance window, a
direction cosine and a lift bound - and it reads the final state from the bundle's `objects`
series rather than from the last timeline sample I was using.

**Which of those explains 11 disagreements is not established.** Candidates:

- a different final position (bundle samples vs my last timeline row)
- `unmoved:target_box_b` failing because the protected box moved
- the minimum displacement floor of 0.03 m against my `push` values
- a direction cosine below 0.9 on some runs

**This has to be resolved before any success figure from this session is quoted again.**

## What is safe to say

- The staging fix is real: staging reports SUCCEEDED 18/18 where it was 0 before, and the
  mechanism (a start-up race) is established at the line.
- The robot moves the box into the zone on at least 7 of 18 runs, verified by the evaluator's own
  task clauses.
- **Every one of those 7 is rejected by the gripper gate**, which rounds 55-58 characterised by
  code path as measuring passive deflection against a threshold sized for commanded closure.

## What is NOT safe to say

- **18/18.** I said that in rounds 81 and 82. The evaluator does not support it and I am
  withdrawing it here rather than leaving it in the record.
- Anything about the rate until the 11 disagreements are understood.

## Status

T08 remains `CALIBRATION_UNSUPPORTED`. **0 of 18 verified.** No capability level claimed.