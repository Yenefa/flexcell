# Trusted-simulation evidence, 2026-10-27

`core-v1/` contains 63 byte-identical copies of raw records from the five declared
velocity_servo/MTC functional tasks. Its copy manifest records every input SHA256/size.
The original batch remains **STOPPED**: its strict JSON reporter rejected the expected
budget failure's unmeasured `NaN` distance after cleanup. Trial 5 has no fabricated
`result.json`. `core-v1-readjudication.json` is a separate fact audit, never a replacement
window receipt or a newly granted qualification. It verifies the four successful task
outcomes, the expected budget failure, one-use goal identities and clean reset/health.

```bash
python3 setup/acceptance/trusted_sim_20261027/verify_core_v1.py
python3 setup/acceptance/trusted_sim_20261027/selftest_core_v1.py
```

`colcon-test-550.log` records the pre-data build/test ladder. The archive does not claim
a success rate, contact grasping, hardware qualification or a historical failure cause.
Large raw rosbag/physics/image streams remain in the run artifact directories and the
GitHub full-stack job artifacts. Later data-window receipts are added separately.

`data-window-v1.json` and `data-roundtrip-v1.json` record the complete five-example data
window and official LeRobot readback (574 frames). The portable dataset is under
`data/examples/trusted_sim_20261027/`. `joint/` and `motion/` retain the native lease /
reattachment and actual MTC cancel / timeout receipts, including clean final health.

`joint-motion-window.json` is the two-task declaration. `joint-motion-traces.zip`
contains both complete synchronous traces, action/skill/carry logs, identity/config and
health. `verify_joint_trace.py` checks every attached sample with no trimming, translation
drift <5 mm and orientation drift <0.05 rad. Measured drift is much smaller; this remains
a small oracle fixture, not a statistical/contact-grasp claim.

```bash
python3 setup/acceptance/trusted_sim_20261027/verify_dataset.py
python3 setup/acceptance/trusted_sim_20261027/verify_joint_trace.py
```
