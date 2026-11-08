# P1.4 stage 1 — 真实 Gazebo 执行（M3-S 链路验证）

- 方式：`run_pilot.py --gazebo-check` 调 `pilot/gazebo.py` → WSL 内 `scripts/sim_smoke.py --case normal`；
- 环境：Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic，`velocity_servo` + `legacy` skill；
- 构建：4 packages，3min04s（首次）；本次运行无重建。

## 结果
| 项 | 值 |
| --- | --- |
| status | **PASS** |
| runtime_fingerprint | `aa5ac4970b9e659a7123ec01099dd64a830e478f86f4f23f2a30731daea60238` |
| world_sha256 | `f78a469d…2bb187` |
| semantic_config_sha256 | `2e49061…f2bc1` |
| physical_tasks_dispatched | 1 |
| task outcome | `OUTCOME_SUCCEEDED` |
| final_position_error_m | **0.00533** |
| evidence_id | `pick_place_v1-6d6dff86` |
| recorder_exit / owned_launch_exit | 0 / 0 |

## 文件
- `result.json`：sim_smoke 完整结果；
- `identity.stdout`：`infra/runtime_identity.py` 输出；
- `episodes/`：episode 证据；`recorder.log`：记录器日志；`m3s.json`：本次采集摘要。

## 边界
- 这是**固定任务**的真实执行（非 Agent 修改任务），证明：**P1.x harness 可以驱动真实 Gazebo 并采集 M3-S 级证据**。
- 尚不是"三臂在 Gazebo 上跑"；下一步做 Gazebo task adapter（把 gate/sim.py 换成 gazebo_sim.py）。
