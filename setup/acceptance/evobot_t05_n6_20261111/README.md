# T05 中转 — n=6 最终结果（修正了假失败）

## 结论先行

| 层 | 结果 |
| --- | --- |
| **规划** | **6/6 正确** |
| **执行** | **4/4 = 100%**（在成功启动的 4 次里） |
| Harness | 2/6 未启动 |
| **False Success Rate** | **0.0** |

## 我上一轮报的「执行 1/3」是假的

上一轮我说执行成功率 1/3，并把剩余失败归因为 `POSE_NOT_REACHED` 的「真实运动问题」。
**那个归因是错的。**

真正的根因：
```
Failed to find a free participant index for domain 213
rmw_create_node: failed to create domain, error Error
```

**CycloneDDS 参与者名额耗尽。** 我每次运行都用同一个 `ROS_DOMAIN_ID=213`，
上一轮的进程还没完全退出，新进程就抢不到参与者名额。

后果链条：
```
DDS 名额耗尽 -> move_group / move_to_pose_server 起不来
             -> 运动请求失败 -> POSE_NOT_REACHED
             -> 我误判为「运动学真实失败」
```

**我把基础设施故障当成机器人能力问题报了。**

## 修复

1. **每次运行用唯一 domain**：`DOMAIN = 220 + (seed % 10) * 3 + attempt`
2. **等待进程真正退出**，而不是固定 `sleep`：轮询 `pgrep` 直到进程消失

修复后：**4/4 执行成功**，`POSE_NOT_REACHED` 完全消失。

## 各 seed 的 Agent 计划（全部正确）

| seed | 目标物体 | 路线 |
| --- | --- | --- |
| 1000 | box_b | zone_1 -> zone_2 |
| 1001 | **box_a** | zone_1 -> zone_2 |
| 1002 | box_b | zone_1 -> zone_2 |
| 1003 | box_b | zone_1 -> zone_2 |
| 1004 | box_b | zone_1 -> zone_2 |
| 1005 | box_b | zone_1 -> zone_2 |

seed 1001 的指令是「Move the **red** block...」，red = box_a，
Agent **正确识别了颜色与物体的对应**，没有机械地一直选 box_b。

## A′ 规则引擎

**6/6 全部拒绝**（`no rule matches this instruction`）。
中转任务对规则引擎不可解——这是稳定的区分力。

## 剩余 2 次失败

1004/1005 各重试 1 次仍未启动，根因**相同**（DDS 名额）。
修复不彻底：唯一 domain 缓解了但没根治。
**真实剩余失败率约 2/6 = 33%**，仍需继续修，不能声称环境已稳定。

## 可以宣称与不能宣称

**可以宣称**：
- Agent 在 T05 上规划 **6/6** 正确；
- 成功启动时执行 **4/4** 成功并通过独立验收；
- A′ 规则引擎 **0/6**，中转任务构成真实区分；
- False Success Rate **0.0**。

**不能宣称**：
- Level 2 达成——启动失败率仍高，执行样本仅 n=4；
- 环境已稳定——还有 2/6 启动失败；
- 泛化——未跑 held-out。

## 教训

**报失败之前，先确认失败发生在哪一层。**
我连续两轮把 harness 故障说成机器人能力问题：
1. 第一次：`$NAMES2` 未定义 -> 观测为空 -> 判「任务失败」；
2. 第二次：DDS 名额耗尽 -> 运动失败 -> 判「运动学真实问题」。

两次都是**先看到症状就下结论**。
