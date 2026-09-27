# REPRODUCE — fresh-machine bring-up (GitHub-only)

> Authoritative portability doc. Everything needed to take a bare Windows
> laptop to a fully verified FlexCell workcell comes from this repository.
> Written for the 2026-09-28 machine switch: RTX 4060 laptop, Core i5-13500H,
> 16 GB RAM.

## 0. Conventions you must keep

- The WSL workspace is `/home/ros/agentic_workcell_ws` (the flexcell repo
  itself - user `ros`, created in phase 1). Hardcoded in the CLI and every
  battery script.
- The staging area is `/mnt/f/flexcell-stage` (drive `F:`). Hardcoded in
  ~50 files (`WORLD=`, `ADMIN=`, all acceptance evidence dirs). On the new
  machine, EITHER assign a partition/drive letter `F:` and copy the staging
  dirs there (phase 3), OR bind-mount any folder onto `/mnt/f`:
  `sudo mkdir -p /mnt/f && sudo mount --bind /mnt/c/flexcell-stage /mnt/f`
  (add to /etc/fstab to survive reboots).
- Behavior-freeze baseline: `setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl`
  — fsm_trace compared byte-exact. Never edit baselines.

## 1. Windows side

1. `wsl --install -d Ubuntu-24.04` (WSL2; `wsl --update` first if WSLg is old).
2. Install the GPU driver (NVIDIA RTX 4060: current Game Ready/Studio driver;
   GPU-PV into WSL is automatic via /dev/dxg - no CUDA needed for rendering).
3. Recommended `C:\Users\<you>\.wslconfig` for a 16 GB host:
   ```
   [wsl2]
   memory=10GB
   swap=16GB
   ```
   (Gazebo Harmonic + rviz2 + MoveIt + 7 python servers comfortably fit in
   10 GB; the i5-13500H's 16 threads handle the load.)
4. Credentials: the repo is private - prepare a GitHub PAT / credential
   manager login before phase 2. If you are behind a proxy (Clash etc.):
   WSL `git clone` needs the proxy reachable (FlClash: enable Allow LAN +
   point WSL git at `http://<host-ip>:7890`), while `api.github.com` may
   need DIRECT (NO_PROXY) - see 踩坑日记 2026-09-26/27 entries.

## 2. WSL bring-up (inside Ubuntu-24.04)

Scripts live in the repo under `scripts/` (clone the repo somewhere on the
Windows side first, or fetch it from WSL directly):

1. `scripts/00_audit.sh` - environment audit (run as any user; rerun after
   phase 1-2 to verify).
2. `sudo bash scripts/01_provision.sh` - creates user `ros` (password `ros`,
   passwordless sudo) and base packages.
3. `sudo bash scripts/02_ros_jazzy.sh` - installs ROS 2 Jazzy + Gazebo
   Harmonic + MoveIt 2 + ros2_control + rosdep (apt retry loop built in;
   needs the network).
4. As `ros`:
   ```
   git clone https://github.com/Yenefa/flexcell.git /home/ros/agentic_workcell_ws
   cd /home/ros/agentic_workcell_ws
   bash scripts/03_build_omx.sh          # imports the 4 ROBOTIS repos per
                                         # agentic_workcell.repos into src/
                                         # (skips existing), builds them
   colcon build --symlink-install --packages-select flexcell_interfaces flexcell_skills
   source /opt/ros/jazzy/setup.bash && source install/setup.bash
   ```
5. Offline test ladder (no GUI needed):
   ```
   python3 src/flexcell/flexcell_skills/test/test_canonical_state.py     # 13
   python3 src/flexcell/flexcell_skills/test/test_decision_policy.py     # 15
   python3 src/flexcell/flexcell_skills/test/test_skill_contract.py      # 13
   python3 src/flexcell/flexcell_skills/test/test_contracts.py           # 17
   python3 src/flexcell/flexcell_skills/test/test_recovery.py            # 15
   python3 setup/82_undefined_attr_check.py src/flexcell                 # static
   ```

## 3. Staging area (F: convention)

Copy from the clone (they are identical to the originals captured in-repo):

```
cp -r /home/ros/agentic_workcell_ws/worlds /mnt/f/flexcell-stage/worlds
cp -r /home/ros/agentic_workcell_ws/setup  /mnt/f/flexcell-stage/setup
sudo chown -R ros:ros /mnt/f/flexcell-stage
```

`setup/flexcell` (the lifecycle CLI) exports `GALLIUM_DRIVER=d3d12` on
purpose: WSLg's XWayland is not DRI3-capable, so without it Mesa falls back
to llvmpipe (rviz2 ~6fps at ~160% CPU - and that CPU burn is what starved
the carry servo in the att1/att2 incidents). With it, glxinfo reports the
real GPU (D3D12 - RTX 4060 / RX 6800).

## 4. Verification ladder (in order; stop at the first red)

1. `bash /tmp/flexcell_cli start` → `START OK` + `flexcell health` = 12 OK
   (~40 s on the 13500H).
2. `flexcell reset` → `"ok": true`.
3. Happy demo:
   `python3 src/flexcell/flexcell_skills/test/w1_client.py --action demo --scenario week1_demo_v1`
   → `OUTCOME_SUCCEEDED`, zone errors ≲ 13 mm, both places genuine
   (`place.jsonl`: released=true + drop-error detail).
4. Parity: the demo's `fsm_trace` must equal
   `setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl`'s
   fsm_trace byte-for-byte (labels are machine-independent; zone errors are
   physics and vary within tolerance).
5. Battery: `bash setup/61_w15_acceptance.sh happy|recovery|exhaust|invalid|reset`
   (evidence lands in the acceptance dir; `attempt` labels in traces are
   frozen - do not "fix" them).
6. Day-2 regression: `bash setup/32_day2_acceptance.sh regression`
   (MOTION_DETECTED = True; run it with the arm OFF the all-zero home - e.g.
   after a demo - or case10's all-joints check structurally fails).

## 5. What is intentionally NOT in the repo

- `.zcode` memory files (machine-local; docs/HANDOFF.md is the traveling
  handoff).
- The C-drive docs repo's .docx acceptance reports (the raw .out/.jsonl
  evidence IS in setup/acceptance/).
- Windows GPU driver setup (machine-specific).
- `workspace/aedl` (separate private repo; its docstring patch sits in that
  project root awaiting a privileged session).

## 6. Known first-run hazards (all in 踩坑日记, dates 2026-09-26/27/28)

- /joint_states must have exactly 1 publisher (joint_state_broadcaster).
- `flexcell reset` may exit RC=139 while reporting `"ok": true` - judge by
  the JSON, not the exit code.
- `setup/32_day2_acceptance.sh` needs an explicit case argument; bare
  invocation is a silent RC=0 no-op.
- Day-2 regression case10 requires the arm OFF the all-zero home (its
  all-joints |>0.05 rad| check structurally fails otherwise).
- Acceptance batteries tolerate servo-starvation retries under load; judge
  by structured evidence, not by eyeball.
