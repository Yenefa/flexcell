# 有类型的组合任务

`/run_composite` (`flexcell_interfaces/action/RunComposite`) 接收一个显式、有界的
搬运链，允许同一对象多次出现。各段复用现有 RunPickPlace 的策略/Skill 执行器；
FSM、Clef、DeepSeek 仍决定段内动作。外层顺序由调用者提供。

## 调用

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 src/flexcell/flexcell_skills/test/w1_client.py \
  --action composite --plan setup/transferbench/composite_swap_v1.json --timeout 360
```

示例计划是 B→缓冲位、A→B 原位、B→A 原位。调用前必须以实际 Observe 确认
计划初态；不能在交换完成后直接再次执行此计划。此命令会驱动机器人，文档中的
命令不构成重复采样许可。

计划包含 `scenario_id`、`initial_objects`、`stages`、`final_empty_positions`、
`position_tolerance_m`、`clearance_m` 和 `motion_profile_id`，不允许额外字段。
阶段数 1..8，stage_id 唯一，对象可重复；所有坐标必须有限。
初态须声明 Observe 中的每一个对象。ROS 位姿只接受 world frame、单位旋转；
位置容差为正数且不超过 0.06m，中心空置距离为 0.05..0.25m。
这些中心距离判据不替代碰撞或实体安全验收。

## 执行与记录

父任务从初态观察到最终联合核验一直持有同一个机械臂 admission 锁；
RunDemo、RunPickPlace 和另一个组合任务会返回 RESOURCE_BUSY，无法插入两段之间。
每段之前新 Observe 核对已提交状态及目标空置，之后新 Observe 核对该段后置状态；
最后单独的新 Observe 同时验证全部最终位置、空置位和 carry 已释放。

每段原生执行都要求确认终态、Verify 有限非负误差、episode 成功写入。
失败、取消、未确认 Skill goal 或观察缺失会阻止下一段。取消在当前 Skill 等待及
段间边界传递；无法确认停止时沿用既有 ownership 隔离，task state 保持 BUSY。

父级 JSONL 位于 `~/.ros/flexcell/composites/`，以独占方式创建；STARTED 在执行前
flush/fsync，COMMITTED 仅在新观察通过后写入。父任务通过 action result 的
`evidence_id` 返回回执路径，另返回已提交 stage IDs、component run IDs 和 UUIDs。
父记录不是 EpisodeSchema；每段仍有自己的原生 policy/Skill episode。

子段在父 action 内直接调用同一个执行器，**没有向 DDS 重新发送 RunPickPlace goal**。
结果字段 `component_goal_uuids` 和子 episode 的 `goal_uuid` 是内部执行关联 ID；
不是独立接受的 DDS action goal。子 episode 明确记录
`execution_kind=IN_PROCESS_COMPONENT`、`component_execution_id`、`parent_run_id`
及 `stage_id`。真实 Skill/controller goal 仍走现有有类型的 action 传输。

进程中断后 STARTED 不能证明阶段成功或已经停止；v1 不自动重放或续跑。
应先确认 ownership、carry 和新测量状态，再提交明确的新计划；旧回执保留。
本接口不改变 reset 行为，也不实现跨进程事务恢复。

## 只读审计

```bash
python3 setup/127_composite_audit.py \
  --receipt /absolute/path/to/composite.jsonl \
  --episodes /absolute/path/to/episode-directory \
  --deployment /absolute/path/to/deployment.json
```

审计重新检查有序父子回执、实际 episode、指纹、逐段条件和最后联合观察；Hybrid
另检查真实模型路由。它不驱动机器人；失败回执始终保留，成功审计不授权补采。
新接口改变 runtime fingerprint，新旧证据不并池。校准绑定的 jev_backends.py
字节不修改；n≥50、AC@90 和实体安全验收继续冻结。
