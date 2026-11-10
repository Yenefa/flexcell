# T02 排除任务 — 两臂对照（同一实例、同一验收器）

**指令：** "Clear the table into the right bin, except the blue block, which must stay put."

## 结果

| 项 | Arm A（确定性） | Arm B（Agent） |
| --- | --- | --- |
| 规划动作 | 只移动 `target_box_a` | 只移动 `target_box_a` |
| 独立验收 | **PASS** | **PASS** |
| 受保护物体位移 | **0.000 m** | **0.000 m** |
| `false_success` | false | false |

两臂都正确地把 `target_box_b` **留在原地**——这是 T02 的核心：**"不动"是答案的一部分**。

## Agent 主动报告了不确定性
> "Interpreting 'right bin' spatially as zone_1 on the robot's right side."

它自己识别出"右"是空间指代，需要解释。**这正是我们想看到的行为**：
不是假装确定，而是标注假设。

## 这次运行暴露并修掉了一个真实缺陷

### 第一次跑：正确执行被判 FAIL
两臂都只移动了 box_a（正确），但验收器判 **FAIL**：
```
objects observed: 1/2, absent: ['target_box_b']
reason: "object missing"
```

**原因**：观测桥只读技能日志，而 `target_box_b` **从未被抓取**，所以日志里没有它的位置。
于是"未观测"被当成了"无法证明未移动"。

### 这是观测设计缺陷，不是机器人问题
两种偷懒做法都不接受：
- 报"absent" → **正确执行被判失败**（当时的实际行为）；
- 假设"没动" → **错误执行会被判通过**。

### 修复：引入 Gazebo ground truth
新增 `capture_ground_truth.py`，通过**技能服务器用的同一个 `sample_gz_pose`** 读取
`gz` 位姿流，覆盖**所有声明的物体**，包括从未被碰过的。

验收器观测中 `_provenance` 现在明确标注来源：`gz.ground_truth` vs `verify.measured`。

新增 5 个回归测试（总计 **42 个离线测试**）。

## 这个结果证明了什么

1. **排除类约束可被验证**："必须不动"现在有实测证据，不是靠假设。
2. **两臂在同一任务上可比**：A 机械推导、B 自主规划，都正确。
3. **Agent 会标注假设**，不是无条件自信。

## 没有证明什么

- n=1 实例。
- **A 与 B 在这一项上没有差异**——T02 太简单，没区分出两臂。
- 未跑 held-out。

## 观察：为什么 A 和 B 都没拉开差距

T02 只需"读指令 → 找出被排除的物体 → 移动剩下的"。
`plan_from_spec` 和 LLM 都能做到。
**要区分两臂，需要任务本身要求 Agent 做机械规则做不到的推理**
（例如 T04 的实例区分，或需要根据观测状态调整计划的任务）。
