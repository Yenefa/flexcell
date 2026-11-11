# 第一个被 EvoBot 实际完成的官方外部 Benchmark 任务

OFFICIAL task · OFFICIAL environment · OFFICIAL predicate · **success = True**

| 项 | 值 |
| --- | --- |
| Benchmark | LIBERO（commit 8f1084e3，MIT） |
| 任务 | libero_object[0] pick_up_the_alphabet_soup_and_place_it_in_the_basket |
| 环境 | libero.libero.envs.OffScreenRenderEnv over robosuite 1.4.1 |
| 判据 | LIBERO 自己的 check_success()，**未改写、未放宽** |
| **官方结果** | **True**（settle 100 步内持续为真） |
| 分类 | **OFFICIAL = true**，ADAPTED = false，EvoBot Native = false |

## 两个根因，都是实验定位的，不是猜的

### 1. 夹爪符号反了

robosuite 约定 **+1 闭合**、-1 张开；我一直用 +1 当张开。

发现方式：标定下探高度时 object_dz 在**所有**高度都是同一个 0.0234 —— 那是重置沉降的假象。
加入**对照臂**（不闭合夹爪）后真相显现：lift_above_control = 0，**从未抓住**。
翻转符号后 0.02/0.04/0.06 三个高度都能抓起（比对照多抬 **0.1137 m**）。

**没有对照臂，我会一直误以为「抓住了但放歪了」。**

### 2. 瞄准了篮体，而不是官方目标区域

| 位置 | z |
| --- | --- |
| basket_1_main（我一直瞄准的） | 0.035 |
| **basket_1_contain_region（官方判据实际测的）** | **0.1068** |

改瞄官方 contain region 后物体落入篮内（最终 [0.021, 0.260, 0.055]），判据为真。

## 控件与方法

- 位姿 → OSC 笛卡尔 delta 适配层，每步重读末端执行器闭环；
- 阶段：approach → descend → close → lift → transport → lower → release → settle → retreat；
- 感知是 **ORACLE**（读仿真器状态，不是相机）→ 这是**执行结果**，不是感知结果；
- EvoBot 自身的 ROS 2 / Gazebo / MoveIt 栈**未被改动**。

## 状态标记

| 项 | 标记 |
| --- | --- |
| 适配层 | IMPLEMENTED |
| 抓取标定（含对照） | SIM_TESTED |
| **官方任务完成** | **SIM_TESTED + 官方判据为真** |
| 独立复核 | verify.py |
| 迁移到第二个官方任务 | **未做** |

## 明确不宣称

- 不宣称这是 EvoBot 的**规划能力**——控制器是脚本化阶段策略，**不是 LLM 规划出来的**；
- 不宣称有感知能力（ORACLE）；
- 不宣称可迁移到其他 LIBERO 任务（未测）；
- 不宣称任何 LIBERO 排行榜成绩。
