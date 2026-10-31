# Pre-attach world-frame repair implementation plan

**Goal:** Enforce the existing at-rest hold while accepting equivalent rotations.

**Architecture:** Preserve relative SE(3) as the carry reference. Retain world
parent/body poses in the runtime history and independently derive them from the
raw offline hold. Use the current spread bounds in each frame. Average unit
quaternions on a common hemisphere. No controller, force or default change.

**Tech stack:** Python, pytest, ROS Jazzy, MTC, Gazebo, existing 2 ms observers.

1. Add common-translation/common-rotation and stationary q/-q tests to
   `src/flexcell/flexcell_skills/test/test_preposition_reference.py` and
   `test_preposition_gate.py`. Run both files on the unmodified implementation
   with WSL Python and `PYTHONPATH=src/flexcell/flexcell_skills`; retain the red log.
2. Modify `flexcell_skills/joint_follow.py`: retain validated world poses in each
   detached sample; check pairwise position and shortest-quaternion-angle spread
   for parent, body and relative transforms; align signs before averaging the
   reference. Record measured world spreads with unchanged bounds.
3. Modify `scripts/preposition_gate.py`: derive world spreads from every raw hold
   step, reject a moving world hold, and average signs consistently. Report old
   missing runtime metadata as unrecorded, never as measured zero. Re-run the
   focused tests and the relevant follow/contact/injection suites.
4. Export a committed LF-only source snapshot to an isolated ext4 runtime stage.
   Preserve the existing dirty WSL checkout. Build/test first-party packages in
   isolated prefixes using the existing locked upstream install; verify source,
   imported Python and native identities before dispatch.
5. Commit a new one-task declaration before execution, retaining the fixed world,
   semantic configuration, 2 ms step, follow/contact/freefall limits and no-retry
   rule. Run once, independently replay all gates, archive complete raw evidence.
6. Obtain a read-only review, fix concrete findings, push the branch and create a
   stacked PR. Open bounded junior issues for status-ledger reconciliation and
   pure-Python parity input validation, with exact files and acceptance tests.
