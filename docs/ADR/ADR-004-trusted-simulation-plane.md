# ADR-004: Reuse manipulation and dataset infrastructure below stable contracts

- Accepted implementation direction, 2026-10-27; qualification is recorded separately.
- Scope: new simulation profiles. Historical protocol v2, raw evidence and the model/n>=50 freeze remain unchanged.

Retain canonical WorldState, interchangeable policies, deterministic admission, executor-owned
recovery, skill postconditions, independent verification and episode provenance. Keep ROS 2
Jazzy, Gazebo Harmonic, MoveIt 2 and the ROBOTIS drivers.

1. Add the official Gazebo DetachableJoint as a **fixed-attachment oracle**, not a contact
   grasp model. Its thin session/lease adapter observes joint components and simulation
   progress; it never creates its own joints or teleports objects. Preserve the named
   teleport and velocity controls. No silent fallback.
2. Plan PICK/PLACE stages with pinned Jazzy MTC 0.1.8. Keep public Action fields unchanged.
   Pass one-use trajectories to the existing MoveToPose executor, sharing arm admission,
   controller ownership, cancellation and measured stop/endpoint checks. Planning-scene
   attach/detach never substitutes for physical engage/release confirmation.
3. Add PR headless simulation smoke on GitHub-hosted CPU runners without GUI, RViz,
   camera or inference. A separate camera/data job has a 30-minute limit. Upload identity,
   startup, task, reset, health, raw bag and 50 Hz synchronous physics observations.
4. Keep Observe as SIMULATION_GROUND_TRUTH. Add a data-only 640x480 RGB camera at 10 Hz,
   causal state/reference alignment within 50 ms and accepted gripper targets. LeRobot
   v0.6.1 owns the learning format; its Python 3.12/NumPy 2/CPU Torch environment is
   isolated from ROS/system NumPy. Preserve raw evidence and original timestamps.
5. Declare windows of at most five logical tasks. Stop on unknown state, missing evidence,
   fingerprint drift or unexpected outcome. Preserve failed episodes without replacement.
   These functional windows do not establish a success rate or policy superiority.

Existing launches and baseline worlds are unchanged. Select carry and skill backends
explicitly. If joint integration is NO_GO, retain it and qualify velocity separately.
Each configuration has a separate fingerprint; never pool it with historical cohorts.

This supersedes the earlier route restrictions only for these new profiles. MTC does not
choose tasks or recovery. BehaviorTree.CPP, cuMotion, Isaac, Tesseract, visual Observe,
hardware and learned policies remain later, evidence-triggered work.
See [implementation status](../TRUSTED_SIMULATION_20261027.md).
