# local_run_20261027

2026-10-27 在 WSL（Ubuntu-24.04，ROS 2 Jazzy，Gazebo Sim 8.15.0，无头）上的一次本地实测。

写入报告在 `docs/CARRY_TELEPORT_20261027.md`；本目录只放原始与派生数据。

| 文件 | 内容 |
| --- | --- |
| `A1.jsonl` | 运行 A 单轮 PICK：成功，rise +0.0764 m |
| `A1b.jsonl` | 运行 A 重复一轮：成功，rise +0.0623 m |
| `A4.jsonl` | 运行 B 四轮：3 成功 / 1 失败（trial 2，code 23，rise −0.0083 m） |
| `demo_poses.jsonl.gz` | 运行 C 完整 demo 的原始位姿流（端到端成功，27.79 s） |
| `health_after_demo.json` | 运行 C demo 结束后的健康检查 |
| `start3.log` `stop3.log` | 运行 C 的起栈 / 停栈日志 || `trajectory.csv` | 运行 A 派生：`t,box_z,gripper_z,delta`，50 Hz |
| `poses.jsonl.gz` | 运行 A 原始位姿流（2208 帧 / 44 s） |
| `poses4.jsonl.gz` | 运行 B 原始位姿流（7372 帧 / 147 s） |
| `start.log` `start2.log` | 两次起栈日志（19 项健康检查） |
| `health_after.json` | 停栈前健康检查 |
| `stop.log` `stop2.log` | 停栈日志 |

采样命令：

```bash
gz topic -e -t /world/empty/dynamic_pose/info -n 9000 --json-output
```

环境：`ROS_DOMAIN_ID=45`、`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`、gz 带 `-s`、MoveIt `start_rviz:=false`、源码 `e7a6963`。

这些数据是**诊断观测**，不是 benchmark 资格；5 轮 1 次失败，不构成失败率估计。
