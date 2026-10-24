# Home GPU: five-case Jev abort regression (2026-10-24)

The fixed batch completed once on runtime source
`29b1cf6551aee3e2ba85dc93a340d32d8729d2aa`:

```bash
python3 setup/94_scenario_runner.py --stage smoke --policy jev --batch S4:2 S5:2 S1:1
```

| Scenario | Count | Actual result | Typed cause / recovery |
| --- | ---: | --- | --- |
| S4 | 2 | Expected FAILED, task code 50 | Both preserve PLACE / ERR_MOTION_FAILED / legacy 30 |
| S5 | 2 | Expected FAILED, task code 51 | Both preserve PICK / ERR_GRASP_FAILED / legacy 23; two attempts, budget 1 |
| S1 | 1 | SUCCEEDED, task code 0 | No recovery; A/B errors 5.62 mm / 8.04 mm |

All five functional cases meet the prescribed result checks. This is four
expected failures and one task success, not a five-task physical success rate.
There was no selective replacement or extra robot episode.

## Source and model evidence

- ROS/Gazebo ran on the current WSL laptop with the freshly built PR overlay.
  Physics used its existing `velocity_servo` magnetic simulation configuration.
- Inference ran on the home AMD Radeon RX 6800 through SSH over Tailscale.
  The per-run profile changes only the endpoint to a loopback SSH forward;
  model weights and calibration are unchanged. The log confirms 33/33 layers
  offloaded to Vulkan. The executable hash and effective arguments are archived.
- The Clef Q8 file was fully hashed on the home computer:
  `8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9`.
  The calibration hash is
  `34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`.
- Five native episodes retain **20 actual Jev decisions and 27,641 recorded
  tokens**. Every decision after the initial no-world OBSERVE bootstrap has
  `source=jev`, `fallback=false`, the expected model/weight/calibration identity,
  and positive measured tokens. The recorded explanation's input-token value
  agrees with the native policy trace for every model call.
- One runtime fingerprint is used throughout:
  `14bb873817cc222f6db7e28fbc6201e6af9d014f697160d8c6e4f0372b06113d`.
  Raw batch and native episode bytes are copied unchanged; `episode_map.json`
  retains original paths and SHA-256 mappings. The manifest hashes the archive.

To recompute the functional, identity, token and shutdown checks without
calling ROS or a model:

```bash
python3 setup/acceptance/home_gpu_abort_20261024/audit.py
```

The old deployment helper hard-codes `server_context_tokens=8192`; the actual
home server used its existing `-c 16384`. Both values are retained and the
discrepancy is explicit in `audit.json`. The observed server arguments and logs
are the evidence for the effective configuration. Complete raw model response
bodies were not recorded, and model replay remains NOT_RUN. This functional
receipt does not assert full manifest/configuration equality or baseline
qualification.

## Shutdown and history

The home inference PID 6432 and its supervising PowerShell process were
confirmed exited at **13:24:21 Asia/Shanghai**. Port 11435 was no longer listening
and no `llama-server.exe` process remained. The controller also stopped its local
ROS/Gazebo stack: zero relevant nodes and actions remained. Process creation
time and executable identity were checked before shutdown; unrelated processes
were not targeted. A heartbeat lease and deadline also guarded the remote run.

Three service-start/log-capture preflights preceded the robot batch, issued no
robot tasks, and were shut down. Their status receipts remain in
`preflight_attempts/`. The five-case batch itself was executed once.

The original 176 episodes were not rerun. Their frozen summaries are unchanged;
the current laptop still lacks their native files, the original desktop is
offline, and the home WSL distribution was not running. Historical episode
recovery and replay remain incomplete, separate from these five new episodes.
