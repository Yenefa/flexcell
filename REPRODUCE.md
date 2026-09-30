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
  dirs there (phase 3), OR bind-mount a folder onto `/mnt/f`:
  `sudo mkdir -p /mnt/f && sudo mount --bind /mnt/c/flexcell-mnt /mnt/f`
  (add to /etc/fstab to survive reboots).
  **Mount the PARENT, not the stage dir itself.** `/mnt/f` must be the
  directory that _contains_ a child named `flexcell-stage`, because the CLI
  hardcodes `/mnt/f/flexcell-stage/...`. Verified 2026-09-29: binding
  `/mnt/c/flexcell-stage` directly onto `/mnt/f` resolves to
  `/mnt/f/worlds/...` and every hardcoded path 404s. Working layout:
  `/mnt/c/flexcell-mnt/flexcell-stage/{setup,worlds}` -> `/mnt/f/flexcell-stage/...`.
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
5. Offline test ladder (no GUI needed) — or just `colcon test
--packages-select flexcell_skills`, which runs every suite since the
   M2.3 audit remediation (wired in via `tests_require`):
   ```
   python3 src/flexcell/flexcell_skills/test/test_canonical_state.py     # 13
   python3 src/flexcell/flexcell_skills/test/test_decision_policy.py     # 15
   python3 src/flexcell/flexcell_skills/test/test_skill_contract.py      # 13
   python3 src/flexcell/flexcell_skills/test/test_contracts.py           # 17
   python3 src/flexcell/flexcell_skills/test/test_recovery.py            # 15
   python3 src/flexcell/flexcell_skills/test/test_runtime_guards.py      # 13
   python3 src/flexcell/flexcell_skills/test/test_episode.py
   python3 src/flexcell/flexcell_skills/test/test_safety_gate.py
   python3 src/flexcell/flexcell_skills/test/test_jev_policy.py
   python3 src/flexcell/flexcell_skills/test/test_metrics.py
   python3 src/flexcell/flexcell_skills/test/test_executor_integration.py
   python3 setup/82_undefined_attr_check.py src/flexcell                 # static
   ```
   Measured on the 2026-09-29 bring-up (i5-13500H, 16 threads, 10 GB WSL):
   `colcon test` → **130 tests, 0 errors, 0 failures, 0 skipped** (~12 s);
   `colcon build` at 4 workers → upstream exit 0 + flexcell exit 0. The static
   scan has one known false positive (`jev_backends.py -> self.name`): `name`
   is a _class_ attribute and the scanner only collects `self.X = ...` stores,
   so it cannot see it — `make_backend('local').name` returns
   `'local-reproduction'` at runtime. Fix the scanner (per-class attribute
   scope); do not "fix" the backends.

## 3. Staging area (F: convention)

Copy from the clone (they are identical to the originals captured in-repo):

```
cp -r /home/ros/agentic_workcell_ws/worlds /mnt/f/flexcell-stage/worlds
cp -r /home/ros/agentic_workcell_ws/setup  /mnt/f/flexcell-stage/setup
sudo chown -R ros:ros /mnt/f/flexcell-stage
```

`setup/flexcell` (the lifecycle CLI) does **not** export any GL driver variable —
an earlier version exported `GALLIUM_DRIVER=d3d12`, which is AMD-specific and is
no longer in the tree. Consequence: on a machine with no working hardware GL
inside WSL (e.g. the NVIDIA driver not installed on the Windows host, so Mesa
falls back to llvmpipe), the stack still starts but burns ~180% CPU in the
Gazebo GUI's software renderer — the documented cause of the att1/att2
carry-servo starvation. Unattended verification MUST therefore launch headless:

1. Gazebo: the upstream bringup passes `gz_args = [world, '.sdf', ' -v 1', ' -r']`,
   which starts `gz sim gui` as well as the server. Add `' -s'` in
   `src/open_manipulator/open_manipulator_bringup/launch/open_manipulator_x_gazebo.launch.py`
   (upstream clone, gitignored — machine-local, not a FlexCell change).
2. RViz: `open_manipulator_x_moveit.launch.py` defaults `start_rviz:=true` and
   `setup/flexcell` does not override it, so rviz2 also starts. Install the CLI
   the way the batteries do
   (`tr -d '\r' < <staging>/setup/flexcell > /tmp/flexcell_cli`) and add
   `start_rviz:=false` to its `open_manipulator_x_moveit.launch.py` line.

Proof after starting: `pgrep -af '[g]z sim'` shows the server only, `pgrep -af '[r]viz2'`
is empty, and the 17-check strict health is `ok: true`.

`rosdep` is **not** required for the happy path, and its index is unreliable from
this network: `rosdep update` failed 12/12 attempts on 2026-09-29 (WSL NAT flakes
toward `raw.githubusercontent.com` — `Errno 101`, TLS handshake timeouts, plus one
`EE certificate key too weak` intercept), so `rosdep install` refuses to run and
the dependency closure is **NOT_VERIFIED** — the same caveat as the delivery host
(workspace WSL-001). The closure is instead evidenced empirically: the
`colcon build` resolves, `colcon test` is green, and the runtime ladder passes.

## 4. Verification ladder (in order; stop at the first red)

Since the M2.3 audit remediation the batteries carry HARD GATES
(`setup/lib_gate.sh`): any failed case exits non-zero, every run writes into
a versioned `sessions/<suite>_<sha>_<ts>/` dir (never overwritten; set
`FLEXCELL_SESSION` to pin one session across the 66 phases), and reset
artifacts are gated on the `gz.msgs.Pose` traceback flood. Machine paths can
be overridden with `FLEXCELL_WS` / `FLEXCELL_STAGE`.

1. `bash /tmp/flexcell_cli start` → `START OK` + strict `flexcell health` with
   **17 checks** `ok: true` and `hard_fail: []` (measured 29 s on the 13500H).
   The `READY: ... (Ns)` lines count _retries_, not seconds — a `(0s)` line
   means "succeeded on the first attempt", not "instant".
2. `flexcell reset` → `"ok": true`.
3. Happy demo under the independent referee (recomputes box_rise /
   zone_error from the raw gz stream and cross-checks the servers' jsonl):
   `python3 setup/92_referee.py --object target_box_a --zone 0.12 -0.15 0.0175 --demo`
   → `"verdict": "CONSISTENT"`.
4. Battery: `bash setup/61_w15_acceptance.sh all` (happy / recovery /
   exhaust — exhaust must return the TYPED `ERR_RECOVERY_EXHAUSTED` — /
   invalid; hard-gated).
5. Day-2 battery: `bash setup/32_day2_acceptance.sh happy_a happy_b
invalid_workspace invalid_quat invalid_profile stale_world ik_unreachable
timeout cancel regression` (hard-gated; case10 needs the arm OFF the
   all-zero home).

## 5. What is intentionally NOT in the repo

- `.zcode` memory files (machine-local; docs/HANDOFF.md is the traveling
  handoff).
- The C-drive docs repo's .docx acceptance reports (the raw .out/.jsonl
  evidence IS in setup/acceptance/).
- Windows GPU driver setup (machine-specific).
- `workspace/aedl` (separate private repo; its docstring patch sits in that
  project root awaiting a privileged session).

## 5b. WSL networking: mirrored mode is REQUIRED here (2026-09-30)

`.wslconfig` sets `networkingMode=mirrored` + `dnsTunneling=true`. This is not a
preference: under the default NAT the campus network sees WSL as a
NAT/proxy-shaped client and the account risks being flagged. Mirrored mode makes
WSL share the host network stack, so its traffic is indistinguishable from
native host traffic. It also fixed WSL egress to github.com (1/5 -> 4/5 HTTPS
here, and it varies).

**Mirrored mode has a cost that must be paid for explicitly.** It exposes every
host adapter inside WSL. On this laptop that means two NICs:

```
eth1  100.77.115.74/32   VPN / tunnel adapter
eth2  10.92.6.94/24      the real uplink
```

With both present, FastDDS forms no participant mesh: `ros2 node list` returns
nothing, the `ros_gz_bridge` never delivers `/clock` or `/joint_states`, and
because everything runs on sim time the `ros_gz_control` activation handshake
stalls, so `flexcell start` dies with `START FAILED: controllers not active`.

The fix is one environment variable, exported for every process in the session:

```bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST   # single-machine workcell
```

That is the Jazzy replacement for the deprecated `ROS_LOCALHOST_ONLY`. Verified
under mirrored mode: `START OK`, 3 controllers active, 20 nodes, `health
ok=true`, `reset ok=true` with both boxes canonical.

Two traps that cost real time here, both fixed by `/tmp/flexcell_env.sh`:

- **`ROS_LOCALHOST_ONLY=1` is not equivalent.** It hangs the start instead of
  failing it, and Jazzy prints a deprecation warning pointing at the variable
  above.
- **The `ros2` CLI blocks when the daemon socket is absent.** `ros2 daemon start`
  reports success and then the daemon shows up late, so a `ros2 node list`
  issued too early hits its full timeout with no output. The flexcell CLI's
  readiness probes go through `ros2`, so the daemon must be up before
  `flexcell start` or every probe reads "not ready".

Cleanup gotcha: a half-stopped stack leaves `ros2 launch ...` (PID X) and
`robot_state_publisher` alive. Pattern kills that omit those two leave the
"pre-existing stack" check refusing every subsequent start - kill by PID.

### Running purely inside WSL (what a handover agent needs)

Nothing in the runtime has to live outside WSL. The repo already contains
everything the stack needs - `setup/flexcell`, `setup/flexcell_admin.py` and
`worlds/flexcell_world.sdf` are all tracked - so the `F:` staging drive and the
`/tmp` scratch copies are optional, not dependencies.

```bash
~/flexcell-up.sh        # bring the stack up, then verify
~/flexcell-down.sh      # stop it
~/flexcell-install.sh   # regenerate the CLI + env (idempotent)
```

`~/flexcell-up.sh` sources `~/.flexcell/env.sh` (the discovery-range variable
above), starts the `ros2` daemon, starts the stack only if it is not already
up, and then reports node count, active controllers and a health check. It
refuses to silently restart a healthy stack, so it is safe to re-run.

Two things it will not do for you, by design:

- **`src/` is gitignored**, so the upstream launch file that carries the
  headless `gz -s` flag is a local edit. `~/flexcell-install.sh` re-applies it
  idempotently and takes a timestamped backup, but if you re-clone `src/` from
  upstream, expect to run the installer again.
- **Process ownership lives in `/tmp/flexcell_lifecycle`** (pid files and logs).
  That is tmpfs on purpose: it is per-boot runtime state, and the CLI recreates
  it on every start. A reboot loses the logs of the previous session, nothing
  else.

## 6. Known first-run hazards (all in 踩坑日记, dates 2026-09-26/27/28/30)

- /joint_states must have exactly 1 publisher (joint_state_broadcaster).
- `flexcell reset` may exit RC=139 while reporting `"ok": true` - judge by
  the JSON, not the exit code.
- `setup/32_day2_acceptance.sh` needs an explicit case argument; bare
  invocation is a silent RC=0 no-op.
- Day-2 regression case10 requires the arm OFF the all-zero home (its
  all-joints |>0.05 rad| check structurally fails otherwise).
- Acceptance batteries tolerate servo-starvation retries under load; judge
  by structured evidence, not by eyeball.
