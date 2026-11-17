# #253 保留场景：前置条件实测（2026-11-16）

> 2026-11-17 更正：下文是原环境、原时点的探测记录。当前缺口不是额度，
> 而是历史模型最终工作区没有归档，以及普通任务回归尚未对接。
> 新入口和状态见 [补齐记录](FOLLOWUP_252_253_20261117.md)。环境来源可用主机与构建凭据，不要求镜像。

结论先说：**这台机器上仿真栈是通的**，`#253` 卡的不是环境，是**没有可冻结的候选**。

重跑命令：

```
python3 experiments/repair_eval_v02/holdout_env_probe.py
```

退出码 0/1，可被批跑器当门用；**跳过的检查不算通过**（`incomplete: true`）。

## 实测结果（连续 4 次通过）

| 前置 | 状态 | 证据 |
| --- | --- | --- |
| Gazebo Sim | OK | `gz sim 8.15.0`（`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`） |
| 无头运行 | OK | `gz sim -s` 加载世界、dartsim 物理插件、`/clock` 稳定 200 Hz |
| OMX overlay | OK | `~/agentic_workcell_ws/install` 已构建，暴露 3 个 `open_manipulator_*` 包 |
| 机械臂能拉起 | OK | `Entity creation successful`，`controller_manager` 应答，spawner 正常退出 |
| MoveIt 2 | OK | `/opt/ros/jazzy` 自带 `moveit_*` |
| GPU | 不需要 | 无 `/dev/dri`；物理不需要渲染，世界仍能加载并推进 |

## 一次差点写错的结论

我先跑的两轮里，`controller_manager` 一直等 `/robot_description`，spawner 三次重试后退出，报

```
RuntimeError: Could not successfully call service /controller_manager/list_controllers after 3 attempts.
```

当时机器上有**我自己上一次被打断的 launch 留下的 `gz sim` 进程**。清掉之后再跑，连续 4 次全部通过。
如果没复跑，我会把「环境不可用」写进协议——那是把探测脚本自己的脏环境当成平台结论。

现在 `holdout_env_probe.py` 会在测量前先清残留进程，并把这个理由写在代码里。

## 所以 #253 真正缺什么

1. **一个冻结的候选**：`holdout.assert_frozen()` 要求先记录候选 SHA，再跑第一个保留场景；
2. 该候选必须来自 `#252` 对着 `DEF-F1-REG` / `DEF-F2-MAP` 真实例跑出的记录——目前只有合成 fixture 的记录；
3. 模型 token 额度（6 槽，按已观测的每槽 1-13k 估算，约 3-8 万）。

环境这一项可以划掉了。
