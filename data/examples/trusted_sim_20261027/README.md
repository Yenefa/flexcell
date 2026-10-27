# Synthetic LeRobot sample

`lerobot-five-episodes.zip` contains a complete official LeRobot v3 dataset written and
read back with LeRobot **0.6.1** in the isolated CPU environment from
`infra/data-environment.lock`: **5 episodes / 574 frames**, one 640x480 RGB stream,
five measured joint positions and five numeric controller/gripper position targets.

Three tasks succeeded; unreachable place and budget exhaustion remain failed examples.
This is a technical data sample, not a success-rate estimate, training result or real-arm
dataset. Observe remained simulation ground truth. Standard timestamps are the 10 Hz
dataset clock; `source.*_sim_ns` preserves all four original source clocks. Episodes
include a declared one-second context on either side of the task, including held-state
frames around the fast budget abort. Original task start/end remain in provenance.

Unzip to a new directory, then load with `LeRobotDataset('flexcell/local-simulation',
root=..., video_backend='pyav')` using the isolated environment. This performs no robot
action. `flexcell_provenance.json` retains run outcomes, action UUIDs, fingerprints,
raw input digests and environment versions. Raw rosbag/PNG/physics streams are separate
run artifacts. CameraInfo calibration was not qualified; this is a data camera sample.

Run the lightweight archive audit with
`python3 setup/acceptance/trusted_sim_20261027/verify_dataset.py`.
