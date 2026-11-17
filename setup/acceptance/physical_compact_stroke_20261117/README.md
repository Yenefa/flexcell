# 30 动作预算下的三段接触推动

同一 Gazebo 场景、任务与 30 动作预算下，紧凑推进连续两次在 27 个动作内完成目标，净位移 **91.358 mm** 和 **91.365 mm**，均通过完整 **9/9** 验收。标准模式在规划阶段拒绝了同样的预算，派发 0 个动作。上一轮在相同初始世界和模型中以 40 动作预算执行过同一位移目标，实际各用 36 个动作。这轮实际派发数少 25%。

| 固定实验槽 | 结果 | 返回后净位移 | 动作数 | Runtime 耗时 |
| --- | --- | ---: | ---: | ---: |
| CONTROL | 预算不足，运动前拒绝 | 0 mm | 0/30 | 0.072 s |
| COMPACT_1 | 三段，9/9 通过 | 91.358 mm | 27/30 | 158.113 s |
| COMPACT_2 | 三段，9/9 通过 | 91.365 mm | 27/30 | 157.558 s |
| ANCHOR | 原两段推动，9/9 通过 | 60.937 mm | 24/40 | 118.353 s |
| REG_NORMAL | 单物体抓放通过，终点误差 7.252 mm | — | — | 14.548 s |
| REG_DUAL | 双物体抓放通过，终点误差 1.647 / 6.076 mm | — | — | 28.361 s |

候选前两个接触检查点仍为 4 和 8 mm。后续检查点间隔至多 8 mm，每段轨迹沿用原约束以及运动中接触检查。两次候选的六段均为 1 次悬停、1 次接近、5 次推进、1 次卸载和 1 次返回；原两段任务的推进各为 8 次。组合任务消费的 8 次返回均满足接触、终态已知、末端就绪和观测新鲜度检查，回执年龄为 28.1–65.8 ms。

紧凑推进由 `task_fsm_server` 的 `contact_push_motion_goal_limit: 10` 显式启用，适用于已登记的 `finger_tcp` 接触后端。规划器按每段最多 10 个动作预留预算，执行器按实际派发扣减。标准上限仍为 13，默认后端为 `legacy`。两项抓放回归使用 `velocity_servo` 与 `legacy`。

实施提交 `b8ce146ef068405a08b0fab567df1a8313633479`，实际执行提交 `58ab8d95d85067a4f3e619b8c1d37b566b4fdaf3`。同一镜像先通过 146 项测试，再完成全部六槽。接口与模块 CI 分别通过，测试集合有重叠。 [固定窗口](https://github.com/Yenefa/flexcell/actions/runs/44167822674) · [模块与 ROS 兼容性](https://github.com/Yenefa/flexcell/actions/runs/44167822462) · [Runtime](https://github.com/Yenefa/flexcell/actions/runs/44167822676)

离线复算校验了全部 517 个原始文件、执行源码与场景哈希，重建四份相同的证据包和验收结果，并逐段核对动作派发与返回回执。归档入口见 [archive.json](archive.json)、[原始结果](results.json) 和 [独立复算](offline_verification.json)。

```bash
python3 setup/acceptance/physical_compact_stroke_20261117/verify_archive.py \
  setup/acceptance/physical_compact_stroke_20261117/raw-44167822674.zip /tmp/compact-stroke-replay
```

证据覆盖一个已公开开发场景中的直立 35 mm 方块、世界 −x 方向，以及两个抓放功能回归。正式基线保持 `NOT_PROMOTED`，正式 T08 保持 `CALIBRATION_UNSUPPORTED`。未见实例、完整任务回归和实体机械臂仍待验收。 [旧 40 动作示例](../physical_reachable_contact_20261113/README.md) · [主线 #235](https://github.com/Yenefa/flexcell/issues/235)
