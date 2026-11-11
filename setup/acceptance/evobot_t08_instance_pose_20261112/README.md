# The benchmark never instantiated a task's declared initial poses - fix and scope

**Date** 2026-11-12 - **Found by** the simulation lane (round 1) - **Scoped, fixed and tested by** the Lead
**Status:** defect CONFIRMED and scoped; fix IMPLEMENTED + Unit Tested; live measurement RUNNING (task-8)

---

## 1. The defect

`sim_profile.profile()` hard-codes the two benchmark blocks:

```
target_box_a -> <pose>0.220000  0.000000 0.0175</pose>
target_box_b -> <pose>0.200000 -0.180000 0.0175</pose>
```

and takes **no object-pose argument** (it accepts `zone_2_pose` only). Nothing in the pipeline reads
`spec.objects[].initial_pose` to *place* anything - `generate_t08.py` only writes the field and
`evaluate.py` only reads it to grade. So a spec whose declared box poses differ from those constants
is **never instantiated**: the run happens in the dev geometry and is then graded against the spec's
geometry.

Consequence, measured: the six `t08_unseen` trials of round 1 ran the dev world and were graded
against unseen geometry, with offsets up to **70.7 mm** on a task whose entire tolerance band is
30-150 mm. Those six verdicts are **INVALID_INFRA (Environment)** and constitute **no generalisation
measurement**. (Round 1 first claimed 0/6 and retracted it once this was found.)

## 2. Scope - narrower than round 1 first said

`scan_pose_scope.py` scans every spec set:

| spec set | specs | affected | worst offenders |
| --- | --- | --- | --- |
| `train` | 72 | **0** | - |
| `val` | 36 | **0** | - |
| `t08_dev` | 3 | **2** | seed2001 63.2 mm, seed2002 53.9 mm |
| `t08_unseen` | 3 | **3** | seed3001 70.7 mm, seed3002 50.0 mm, seed3000 31.6 mm |
| `held_out/public` | 36 | **0** | - |
| **total affected** | | **5** | |

**The T01-T06 families are not affected**, because they vary the **zone** (which `sim_profile` *does*
accept via `zone_2_pose`) and keep the box poses fixed. That means:

- the earlier **held-out n6 result is NOT contaminated** by this defect - one less thing to doubt;
- **round 1's wording (no task has ever been instantiated at its declared pose) was too broad and is
  withdrawn.** Five specs were affected, all T08, not the whole benchmark;
- `t08_dev` seed2001 and seed2002 have **never been run correctly** either - only seed2000 coincides
  with the hard-coded world, which is exactly the one the round-1 dev table used.

## 3. The fix - edit the copy, not the frozen generator

`inject_instance_poses.py` rewrites the two `<pose>` elements in the **generated world copy** from the
task spec. `sim_profile.py` stays **byte-identical**; the world is post-processed after generation,
exactly the pattern `inject_contact_evidence.py` already established for the ContactTrace plugin.

It **refuses** rather than degrading:

| Condition | Behaviour |
| --- | --- |
| a spec object has no matching `<model>` | REFUSED - skipping it would leave the instance uninstantiated, i.e. reproduce the defect |
| a pose is not three finite numbers | REFUSED |
| the spec has no `objects[]` | REFUSED |
| the re-read does not match what it wrote | FAILED, non-zero exit |

That last one is deliberate: **a write that is believed rather than verified is the exact failure class
this project keeps finding.** The tool re-reads the file and asserts its own effect.

## 4. Verification done offline (no Gazebo)

| Check | Result |
| --- | --- |
| `test_inject_instance_poses.py` | **7 passed** - moves one object, moves both, never touches a model absent from the spec, refuses on missing model, refuses on non-finite pose, refuses on spec with no objects, dev spec is a semantic no-op |
| integration on seed3001 (worst case, 70.7 mm) | poses land exactly; checkpoint prints `INSTANCE_POSES_OK`; `instance_poses.json` shows `declared == spawned` for both objects |
| dev spec seed2000 | rewriting is a semantic no-op, as it must be (its poses already match the world) |

## 4b. Zone markers are moved too (found by the sim lane, fixed rather than noted)

The sim lane pointed out, correctly, that the fix above instantiates the **objects** but left the
world's **zone markers** hard-coded (`zone_1` at (0.12, −0.15), `zone_2` at (0.25, 0.05)) while a
T08 spec declares `zone_push` at (0.11, 0.03). Grading was never affected — `evaluate.py` uses the
spec's coordinates and the push is open-loop — but the instruction literally says *"push the red
block into the marked zone"*, and the mark on the table was in the wrong place.

Fixed in the same tool rather than filed as a note:

| Behaviour | Detail |
| --- | --- |
| spec zones map by index | spec zone *i* → world marker `zone_<i>` |
| marker z is a **display** height | the spec's zone z is the *block's* height (0.0175); a flat marker using it would float 17.5 mm above the table, so x,y come from the spec and z is `MARKER_Z = 0.001` |
| a marker the spec does not account for is **parked** below the table | `z = −1.0`, no collision, and named in the output — better than leaving a destination the task does not have |
| a spec zone with **no** marker | warning printed, placement reported as `placed: false` rather than silently skipped |

**This cannot change a verdict** and it is recorded as a display fix, not a measurement fix. Its
value is that anything built on the marker later — vision, a demo, a human watching — is not built
on a false statement about the task.

## 5. Driver integration

`run_batch_v2.sh` = the round-1 driver with **step 2b** inserted after the ContactTrace injection:

1. `inject_instance_poses.py "$WORLD" "$TASK"` -> on failure the trial is `INVALID_INFRA instance_poses_failed`
2. write `instance_poses.json` recording, per object, `declared` / `spawned` / `match`
3. if any `match` is false -> `INVALID_INFRA instance_poses_mismatch`

`sim_profile.py`, `evaluate.py`, `verify.py`, `push.py` and every task spec are **unmodified**; the
driver also hashes `sim_profile.py` into the run manifest as before.

## 6. What this unblocks

With poses actually instantiated, `t08_unseen` becomes a genuinely frozen unseen set for the first
time, and `t08_dev` seed2001/seed2002 become runnable. Round 1 has **no** generalisation measurement;
after task-8 the project will have its first one - pass or fail.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_t08_instance_pose_20261112/scan_pose_scope.py
python3 setup/acceptance/evobot_t08_instance_pose_20261112/test_inject_instance_poses.py
```

Both run without a simulator. The scope scanner refuses (exit 1) if it finds zero affected specs,
because that would mean it was looking in the wrong place rather than that the defect was gone.