# A CONFIRMED FALSE FAILURE: the task succeeded and the verifier rejected it

`T08-push-seed3001`, single staged push, frozen evaluator `0.5.0`, evidence status
`COMPLETE_EVIDENCE_CONTRADICTS_PUSH`.

## The four states, kept separate

| state | verdict | basis |
| --- | --- | --- |
| `planning_correct` | **yes** | push toward -x for 0.040 m at contact height 0.020 to place the box in `zone_push` |
| `execution_succeeded` | **yes** | box finished at (0.12584, -0.05326), **0.01725 m** from the zone centre against a 0.06 radius |
| `independent_evaluation_passed` | **no** | `gripper` gate: 0.0032 rad against a 0.0020 limit |
| `agent_claimed_success` | **false** | not claimed |

## Both task clauses pass

```
clause unmoved:target_box_b -> True
clause push:target_box_a    -> True
terminal_passed             True
```

- moved **0.1052 m** (window 0.03-0.15)
- direction cosine **+0.9887** (minimum 0.9)
- landed **0.01725 m** from the zone centre (radius 0.06)
- protected box `target_box_b` unmoved

**By every clause the task defines, this run succeeded.**

## What rejected it

```
gripper :: gripper aperture changed by 0.0032 rad during the window (limit 0.0020);
           fingers closing on an object is a grasp, not a push
```

**1.2 mrad over the limit.**

## That 3.2 mrad is measured passive deflection, not a grasp

Established in `GRIPPER_IS_MEASURED_JOINT_STATE_20261112.md`:

- `observe_server.py:214` sets `gripper_position` from `/joint_states`, i.e. **measured joint
  position** - not a command echo, not a target.
- `push_server.py:20-26` establishes the gripper is **never commanded** during a push, and that
  is required: a push must be distinguishable from a carry.

**Neither finger was ever commanded. Both appear in the contact trace. The aperture moved
because the box pressed on the fingers while being pushed.**

## Why this is a false failure rather than a strict-but-correct verdict

The 0.0020 rad limit exists to detect a **commanded grasp** - fingers closing to carry the
object. Applied to **passive** fingers being deflected by the object they are pushing, it
measures contact, not intent, and rejects a correct push.

This is precisely the failure the objective already records - "gripper gate known to
false-reject correct pushes" - now with a run, a mechanism, and a number.

## What was not done

- The 0.0020 limit was **not** relaxed. Relaxing it would make the gate unable to catch a real
  grasp and is a frozen-file change requiring human approval.
- No evidence deleted; the two-push run that preceded this one remains in the tree.
- Nothing is claimed as independently verified: the verifier rejected this run.

## The evidence artefacts

`/tmp/onepush/tl.json` - 269 samples across one push
`/tmp/onepush/contact_steps.jsonl` - contact trace, 5 partners including both gripper links
`/tmp/op_f.json` - the bundle that was judged