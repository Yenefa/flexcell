# EvoBot 能力阶梯

> **本文档由 experiments/baselines/capability_ladder.py 生成，请勿手工编辑。**
> 每个数字都从归档证据读取或在此重算。重生成命令：
> ```bash
> python3 experiments/baselines/capability_ladder.py
> ```

## 仓库当前状态（重算，不是抄写）

| 项 | 值 |
| --- | --- |
| 证据批次（有效） | 34 |
| 证据批次（已取代但保留） | 7 |
| 批次验证器失败数 | **0** |
| 离线测试 | **238** |

## 两个失败方向，都必须测

只测一个方向，另一个方向会伪装成完美。

| 指标 | 含义 | 实测 |
| --- | --- | --- |
| **False Success** | agent 说成功，世界没成 | **0/48** |
| **False Failure**（任务层） | 任务说失败，世界成了 | **5/48** |

> 使命要求 False Success Rate 为 0：**在当前实测样本上满足**。
> 但区间上界不为 0，且**无声明时该比率不可测量**——那不是 0。

## 通过率（合并两个基础批次，Wilson 95%）

| 臂 | 通过 | 区间 |
| --- | --- | --- |
| **B** 首试 | **30/32 = 93.8%** | 79.9–98.3% |
| **R** 最终 | **32/32 = 100.0%** | 89.3–100.0% |

逐批：

| 批次 | n | B | R | 增益 | 重试 | 通过后仍重试 | 任务层误报 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| batch1 seeds7500 | 16 | 14 | 16 | 2 | 2 | **0** | 0 |
| batch2 seeds8100 | 16 | 16 | 16 | 0 | 2 | **2** | 2 |
| batch3 seeds8100 +goal_check | 16 | 13 | 15 | 2 | 3 | **0** | 3 |

## 阶梯

状态是基于**同行写明的测量**下的判断；阈值写在旁边，可以不同意。

| 级别 | 名称 | 状态 | 依据（可复核） |
| --- | --- | --- | --- |
| 1 | Execute | **已验证** | T01–T06 回归 6/6→6/6，无倒退 |
| 2 | Compose | **部分** | T05 中转 6/6，仅单类组合 |
| 3 | Recover | **已验证（有界）** | 合并 32 例，R=32 高于 B=30；goal_check A/B 已验证 |
| 4 | Develop | **未达成** | 无 Agent 自建新技能 |
| 5 | Improve | **待人工批准** | 提案已预注册、依据已更正，**未实施** |
| 6 | Learn | **骨架** | 经验库+诊断+回归门，Unit Tested |
| 7 | Transfer | **未观察到** | 经验不改变计划（16/16 计划字节相同） |
| 8 | Generalize | **已验证（有限）** | 全新种子 8100/8200 与 7500 区间重叠 |

## 提案状态（读自 JSON，不靠记忆）

| 文件 | 已批准 | 状态 |
| --- | --- | --- |
| actuator_stall_preregistration.json | None | basis superseded |
| release_confirmation_preregistration.json | False | PROPOSED - awaiting human approval, not implemented |

## 当前唯一根因

9/9 次释放失败签名完全一致（跨两批）：

```
place.released                  = False
place.carry_release_confirmed   = True    <- 物体其实已释放
place.gripper_open.reached_goal = False   <- 夹爪没张到位
place.gripper_open.classification = GRASP_STALLED
```

**技能层只看夹爪，于是把成功的释放判成失败。**

现有缓解：runtime/recovery/goal_check.py 在决策层用**计划自带容差**验证世界，
误报不再触发无意义重试（A/B：2 → 0，增益未丢）。
**技能层本身未修，需人工批准。**

## 不许含糊的几条

- **不可测量的零不是零。** 无声明时 false success 不可测量，守卫拒绝出数。
- **靠悲观换来的零不是修复。** v2/v3 prompt 那样做过，已拒绝。
- **修改固定文件必须走变更日志。** 未登记则拒绝重新冻结。
- **没跑过的步骤不能算跑过。** 批次校验器查步骤是否执行，而非数字是否好看。
- **旧运行器保留缺陷作证据。** 修掉它就是篡改记录。
- **一个方向为零不代表可靠。** 反方向一直在 6% 左右。

## 未达成

- Level 4 Develop、Level 5 Improve（待批准）、Level 7 Transfer。
- 技能层误报：**根因已定位，未修复**。
- 多段往返任务的**顺序**判定未解决；goal_check 只是拒绝误判。
- 未上真机（M0）；无采购、无合并。
