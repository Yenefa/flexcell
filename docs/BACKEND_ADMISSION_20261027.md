# 后端准入实测：DetachableJoint（2026-10-27）

对应 issue-04 / issue-05。环境：Gazebo Sim **8.15.0**（ROS 2 Jazzy 自带 vendor 包），无头服务器模式，`GZ_PARTITION` 随机，独立世界，未接触任何在跑栈。

- 世界：`worlds/detachable_probe.sdf`，sha256 `07de5f00cd17813958c139acc50c016d98ff23f2c80d6db30c979d743d2b64aa`
- 探针：`setup/113_carry_backend_spike.py`
- 原始结果：`setup/acceptance/backend_admission_20261027/spike.json`

## 结论

**GO_CANDIDATE——六项断言全部通过。** 但这是"静态父体 + 无机械臂"条件下的准入，不等于整机可用。

| 检查 | 结果 | 观测 |
| --- | --- | --- |
| 初始附着保持 | PASS | 2 s 内 z 稳定在 0.3000 m |
| 脱离后自由落体 | PASS | 25 帧拟合 **a = −9.80 m/s²**（跨 0.48 s） |
| 5 次 attach→detach→re-attach | PASS | **5/5** 跟随，每次位移 +0.0500 m |
| 刚体跟随（10 步瞬移） | PASS | 最大跟踪误差 **0.0000 m** |
| A/B 通道独立 | PASS | 脱离的 A 位移 0.0000 m，附着的 B 位移 +0.0500 m |
| 接触状态下 attach | 记录（不作断言） | 箱子静置在父体上 1 s 后 attach：**成功**，跟随正常，跳变 0.0001 m（`spike.json` 的 `jump` 字段） |

## 三个与文档不一致的地方（这才是 W1–2 真正的风险）

1. **参数名**：8.15 的插件要求 `<child_link>`，而 sim 8 在线文档写的是 `<child_model_link>`。
   用文档的名字会得到一行 `[Err] 'child_link' is a required parameter ... Failed to initialize.`，插件不加载、不建关节，但世界照常启动——**不报错、不崩溃，只是什么都没发生**。
   二进制字符串核对：`child_link`、`child_model`、`parent_link`、`attach_topic`、`detach_topic`、`output_topic`；不存在 `child_model_link`。

2. **模型声明顺序**：子模型必须写在父模型**之前**。否则加载期报 `Child Model probe_box_a could not be found`，同样不建关节、不中断启动。

3. **接触状态可 attach（与文档相反）**：文档明确写"父子接触时 reattach 不受支持"，但本次实测在箱子静置于父体上 1 s 后 attach 成功。
   **不要据此推翻文档**：这是"静止放在顶上"，不是"夹爪侧向夹住"；真实抓取时的接触更复杂。记为"本版本上未复现该限制，需在整机场景复核"，而不是"文档错了"。

另外一条不是文档问题、但会浪费半天：`gz topic -p` 的参数是**消息文本**，发空消息要写 `-p ""`，只写 `-p` 会把后一个参数吃掉并报 `unexpected argument`。

## 这次没有验证的（明确列出，避免被当成已验证）

- 父体是**静态模型**，靠 `set_pose` 瞬移模拟机械臂；真实臂的运动学、控制器时延、500 ms 租约都没参与。
- 接触场景只有"放在顶上"，没有"侧向夹持"。
- 没有双物体同时搬运（只验证了通道互不干扰）。
- 没有与 legacy Pick/Place 兼容性回归（那是 issue-07）。
- 没有验证 `self_collide` 相关行为（脱离后与父体碰撞的场景）。
- **步长标称不一致**：世界写 `max_step_size 0.005`（5 ms）、`real_time_update_rate 500`，两个标签对不上（前者是步长，后者是迭代率；标称 RTF 也不是 1）。判据里的"500 Hz"在签 GO 前要改成"5 ms 步长"或实测迭代率，二者只能选一个写进验收。
- **接触力未测**：判据 4 的"接触力无 NaN"本次没有订阅任何接触力话题，只证明了位姿连续，不要当成已经验过。

## D3 判据表（可直接填）

| # | 判据 | 本次实测 | 结论 |
| --- | --- | --- | --- |
| 1 | 5 次 attach→detach→re-attach 无失败，且 attach 前不接触 | 5/5，每次间隔 0.2 m | 通过（本探针条件） |
| 2 | 绑定后 10 s 内平移漂移 <2 mm、旋转 <1° | 10 步瞬移，误差 0.0000 m | 通过（静态父体） |
| 3 | detach 后 0.5 s 内自由落体，a 在 −9.8±20% | −9.80 m/s² | 通过 |
| 4 | 500 Hz 下无发散：无 >1 m 跳变、无 NaN | 最大跳变 0.0001 m | 通过（仅位姿，未订阅接触力） |
| 5 | legacy 在**不放宽容差**下通过 | 未测 | **待补** |
| 6 | A/B 独立 attach/detach，退役会话不复用 | 通道独立通过；会话语义未测 | 部分 |

**判据 5 与 6 的后半段必须在整机上补**，否则不能签 GO。本探针只回答"这个后端在未来世界里能不能按契约工作"，不回答"接进现有 carry_server 后还成不成立"。

## 复跑

```bash
source /opt/ros/jazzy/setup.bash
python3 setup/113_carry_backend_spike.py --out /tmp/spike.json
```

约 45 秒，退出码 0 表示六项断言通过。加 `--keep-log` 保留 Gazebo 日志。
