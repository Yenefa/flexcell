# 位置效应的真正根因：孤儿进程泄漏（2026-11-11 21:00）

## 一句话

**不是「机器状态退化」这种模糊说法。是 `evobot_run_b.sh` 的清理列表漏了 skill 节点，
每个实例泄漏 6 个进程，累积 36 个之后把下一实例的 carry servo 饿死。**

## 证据

在 A-v2 批次跑到第 8 个实例时检查进程表：

| 进程 | 残留数 |
| --- | --- |
| verify_server | 8 |
| place_server | 8 |
| pick_server | 8 |
| observe_server | 8 |
| move_to_pose_server | 8 |
| carry_server | 8 |

**合计 36 个孤儿**，最老的已运行 896 秒（来自 8 个实例之前）。

`evobot_run_b.sh` 原来的清理行只杀 `gz sim` / `ros2 launch` / `task_fsm_server` / `sim_smoke` /
`move_group` / `ros2 daemon`——**不含 carry/pick/place/observe/verify/move_to_pose 这六个节点**。
杀 launch 父进程不会杀死这些子节点，它们被 re-parent 后继续空转。

## 这解释了此前所有观察

| 现象 | 用孤儿泄漏解释 |
| --- | --- |
| 通过率随执行位置单调下降（100/94/50/0%） | 孤儿数随实例数线性增长 |
| `set_pose rejected` 与判定完全对应 | carry servo 被同类孤儿抢占 CPU，pin 超时 |
| `carry_server.py:571-578` 连续 3 次失败即 abort | 是**症状**，不是根因 |
| T06 放到最前面 3/3 通过 | 冷启动时孤儿数为 0 |
| 容差 0.02 vs 0.06 结果完全一样 | 容差与孤儿无关，当然一样 |

## 修法

在 `evobot_run_b.sh` 的清理段显式列出每个节点名：

    pkill -9 -f "[c]arry_server"; pkill -9 -f "[p]ick_server"
    pkill -9 -f "[p]lace_server"; pkill -9 -f "[o]bserve_server"
    pkill -9 -f "[v]erify_server"; pkill -9 -f "[m]ove_to_pose_server"

加 `[c]` 这类中括号是必要的：不加的话 `pkill -f carry_server` 会匹配到自己这条命令行。

## 为什么之前没发现

负载门控把它**掩盖**了：门控让每个实例等到 loadavg < 3.0 才开跑，
所以实例**开始**时负载是低的。但孤儿从未被清除，它们累计占用的 CPU 是持续的。
门控降低了症状频率，同时让根因更难看见——**这是一个重要的教训：缓冲症状会掩盖病因**。

## 影响

- A-v0 的 61.1% 与 A-v2 前 8 个实例的结果**都不可用于跨模板比较**：不同位置的实例
  面对不同数量的孤儿。
- 每个实例必须从**孤儿数为 0** 的状态开始，这是可比性的前提。
- 已修 runner，已清理全部孤儿，批次从零重跑。

## 待验证

修复后重跑的 72 个实例，若每个实例都在孤儿数 = 0 下开始，
则「通过率随位置下降」应当**消失**。如果它仍然出现，说明还有别的累积源。
