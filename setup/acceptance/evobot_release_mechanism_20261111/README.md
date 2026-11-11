# 根因确定：技能层把「夹爪没张到位」当成「释放失败」

## 9 例，跨两批，签名**完全一致**

| 字段 | 值 |
| --- | --- |
| `place.released` | **False** |
| `place.carry_release_confirmed` | **True** ← 物体已从承载中释放 |
| `place.gripper_open.reached_goal` | False |
| `place.gripper_open.stalled` | True |
| `classification` | **GRASP_STALLED** |
| `position` / `requested` | -0.011 / 0.02 |

```
detail: "gripper did not open (position=-0.011 requested=0.02 stalled=True)"
```

**同一条记录里两个互相矛盾的信号**：承载层说「已释放」，夹爪说「没张到位」。
技能层**只采信夹爪**，于是把一次**成功的释放**判成失败。

## 这解释了之前所有异常

| 现象 | 解释 |
| --- | --- |
| 箱子明明已在目标区，任务却说失败 | 释放成功，夹爪 stall |
| `place.box_after = None` | 失败路径不记录位置 |
| 观测只能退回 `verify.jsonl` | 同上 |
| 恢复重试一个已完成的放置 | 恢复读 `task.out` |

## 我之前的提案是错的，并已更正

**旧提案** `bounded_release_retry`：假定「释放失败 = 物体没被释放」，
所以**重发释放命令**会有帮助。

**9/9 的证据否定了这个前提**：`carry_release_confirmed` 全是 `True`。
**对已经发生的释放重发命令不可能改变结果。**

所以那份预注册已标注 `superseded_basis`，**不是撤回，是依据错误、不可据此实施**。

## 新提案（已预注册，**未实施**）

`evolution/proposals/release_confirmation_preregistration.json`

**改动**：以 `carry_release_confirmed` 作为释放成功的判据；
夹爪 stall 降级为「成功但降级」的属性，而不是失败。

**预测**：

| 指标 | 预测 |
| --- | --- |
| 技能层释放失败 | 9 → **0** |
| 任务层 false failure | 6.2% → **0%**（同实例） |
| 最终通过率 | **不变或上升，绝不允许下降** |
| `place.box_after` 记录 | 恢复可用（测量溯源改善） |

**证伪条件**（任一出现即必须回滚）：

1. 世界未满足目标却报成功；
2. 最终通过数下降；
3. 出现非零 false success；
4. 夹爪 stall 被**隐藏**而不是重分类。

## 为什么这不构成「制造成功」

| 事实 | 说明 |
| --- | --- |
| 验收器 | **不读技能自述，只测世界** |
| 世界测量 | **完全不变** |
| 改动效果 | 只能让**成功的世界**不再被叫做失败 |
| 改动范围 | `place_server.py` 的自述判据 |

重分类自述**不可能让失败的世界变成通过**。
但它**能让 agent 不再重复无用功**——这是真实的能力提升。

## 本轮没有实施的，以及为什么

`requires_human_approval: true`，`approved: false`。

**我自己不能批准自己的提案**——这条规则我从头守到现在。
技能层是机器人的执行代码，改动需人工确认。

## 已经生效的缓解

`goal_check`（上轮验证）已在**决策层**消除这个缺陷的后果：
误报不再触发无意义重试（2 → 0），且未丢失任何增益。

**技能层的病还在，但 agent 已经学会不被它误导。**

## 状态

| 项 | 值 |
| --- | --- |
| 封存 | `BLOCKED_GOOD` |
| 验收器 | **未改** |
| 技能层 | **未改** |
| 改动 | 仅新增预注册 JSON 与取证脚本 |

## 不宣称

- 不宣称 9/9 覆盖全部释放失败（只覆盖两批已归档运行）；
- 不宣称新提案一定有效（**未实施、未验证**）；
- 不宣称 `carry_release_confirmed` 在所有任务里都可靠（只在本任务族观测）；
- **未上真机，M0**。
