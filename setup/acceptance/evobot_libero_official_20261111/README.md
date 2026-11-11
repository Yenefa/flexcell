# 第一个真实外部 Benchmark 接入：LIBERO（Official）

## 分类声明（三者严格区分）

| 类别 | 状态 |
| --- | --- |
| **Official** | **是** —— 官方 BDDL 任务、官方环境类、官方 init 状态、官方成功判据 |
| Adapted | 否 |
| EvoBot Native | 否 |

**没有借用官方名义给自建成绩贴金。** 这条链路上没有一块是我重新实现或重新打分的。

## 固定元数据

| 项 | 值 |
| --- | --- |
| 仓库 | https://github.com/Lifelong-Robot-Learning/LIBERO |
| **commit** | **8f1084e3132a39270c3a13ebe37270a43ece2a01**（2025-03-15） |
| 许可证 | **MIT** |
| 套件/任务数 | libero_object 10、libero_spatial 10、libero_goal 10、libero_10 10、libero_90 90 |
| 已跑任务 | libero_object[0] `pick_up_the_alphabet_soup_and_place_it_in_the_basket` |

## 输入输出格式与成功标准（官方，未改写）

| 项 | 值 |
| --- | --- |
| 观测 | 官方环境返回 dict（agentview_image、robot0_eef_pos/quat、gripper_qpos、joint_pos…） |
| 动作 | **7 维连续**：OSC delta pose(6) + gripper(1) |
| 成功 | env.check_success()，即官方对 BDDL (:goal ...) 的谓词求值 |

## 隔离方式

独立 venv /home/ros/ext-bench/venv-libero（robosuite 1.4.1 + mujoco 3.2.7 + torch CPU），
MUJOCO_GL=osmesa（本机**无 GPU**）。

**EvoBot 自身的 ROS 2 / Gazebo / MoveIt 栈完全未被改动。**

## 已证 / 未证

| 项 | 状态 |
| --- | --- |
| 官方任务可加载（BDDL 解析、环境构建、init 状态载入） | **已证** |
| 可执行并可读官方成功标志 | **已证**（no-op 策略 → False，方向正确） |
| **EvoBot 能控制该环境完成任务** | **未做** |
| 迁移到现有 OpenMANIPULATOR-X 平台 | **未做，且有真实限制** |

## 可行性分层

| 层 | 判断 |
| --- | --- |
| 加载任务 + 环境 + 成功判据 | **可运行（已证）** |
| 用脚本策略完成任务 | 可行（需接入策略，未做） |
| 用 EvoBot 的 LLM 规划器控制 | **需适配**：LIBERO 动作是笛卡尔 delta，EvoBot 规划器输出具体位姿，需转换层 |
| 用现有机械臂硬件复现 | **不可行**：LIBERO 用 7 自由度 Panda + 平行夹爪；OpenMANIPULATOR-X 自由度更低，开炉/抽屉/堆叠等任务无法等价复现 |
| 双臂 / 移动底盘 / 灵巧手类任务 | **BLOCKED**：本平台无对应硬件，不得模拟不存在的自由度 |

## 状态标记

| 阶段 | 标记 |
| --- | --- |
| 外部任务加载器 + 适配接口 | **IMPLEMENTED** |
| 环境构建 + 官方判据读取 | **SIM_TESTED** |
| 独立复核（verify.py 可脱离本会话重跑） | **INDEPENDENTLY_VERIFIED** |
| EvoBot 控制外部环境完成任务 | **BLOCKED**（下一步） |

## 不宣称

- 不宣称「已接入并跑出成绩」——**只跑了 no-op 策略**，成功率 0 是设计使然，不是性能；
- 不宣称 LIBERO 成绩等同于 EvoBot 成绩；
- 不宣称 LADDER / ManiSkill3 / RLBench / RoboCasa / BEHAVIOR 已评估（**未做**）。
