# W7 跨本体迁移 — 设计（M0）与阻塞声明

> 现状：项目只有 OpenMANIPULATOR-X 一个本体（Gazebo + 真实机均未具备第二平台）。
> 本文是**设计**，不是跨本体证据；任何"跨本体成功"的宣称都必须等到第二个本体真实可用。

## 1. 可复用的上层（跨本体应保持不变）
| 层 | 资产 | 为什么可复用 |
| --- | --- | --- |
| Skill 契约 | `PickObject`、`PlaceObject`、`Observe`、`VerifyObject`、`MoveToPose`、`RunDemo`、`RunComposite` | 动作语义与目标都由类型化字段表达，不含 URDF 细节 |
| 约束 | `TaskConstraints`（recovery_budget、verify_tolerance_m、motion_profile_id、max_world_age_s） | 以"行为要求"而非关节空间表达 |
| 世界模型 | `WorldState` / `WorldObject` / `ZoneState` / `RobotStateSummary` | 对象位姿 + 机器人摘要，不绑定运动学 |
| 决策层 | `DecisionPolicy`（FSM / JEV / LLM / Hybrid） | 只消费 WorldState/Goal/Constraints |
| 证据层 | Episode 记录、runtime fingerprint、canonical serialization | 与本体无关的审计格式 |
| 验收语义 | 后置条件（位姿误差、zone 归属、carry 状态） | 判据是任务结果，不是控制细节 |

## 2. 必须替换的适配器层（换本体时优先只改这里）
| 适配点 | 当前实现 | 第二本体的工作需要 |
| --- | --- | --- |
| 机器人描述 | `open_manipulator_description` URDF/xacro | 新本体 URDF + 关节/夹爪参数 |
| 控制器接口 | `velocity_servo` / `detachable_joint` 后端 | 位置/力矩接口适配、抓取机构（吸盘/夹爪）适配 |
| 技能实现 | pick/place/verify server 的 `skill_backend`（legacy / mtc） | 标定 IK 帧、夹爪开合、抓取点 |
| 参数 | `week1.yaml`：zones、reach、motion profiles、速度/加速度 | 新本体的可达范围与安全限位 |
| 感知标定 | 相机内参/外参、AprilTag 尺寸 | 新相机与安装位置 |

## 3. 验证协议（未来第二个本体可用时）
**入口门（必须全部通过）**：
1. 契约不变：8 个 action 字段与语义不改（只允许新增可选字段）；
2. 单元/集成测试通过：canonical state、episode replay、技能后置条件；
3. 同场景 S1–S5 在第二本体上独立验收 PASS。

**指标（TransferBench 风格）**：
| 指标 | 定义 |
| --- | --- |
| 成功率 | 同场景组在两个本体上的 PASS 比例 |
| 迁移成本 | 只改适配器层时涉及的**文件数/参数数**（越少越好） |
| 适应时间 | 从拿到新本体到首个 PASS 的 wall clock / 迭代数 |
| 回归损失 | 第一本体原有场景的成功率变化（必须为 0） |
| 恢复成本 | 新本体上 recovery 场景的额外预算消耗 |

## 4. 当前阻塞
- **无第二机器人本体**（无第二 URDF/仿真模型、无第二台真机）；
- 因此 W7 保持 **M0（设计）**；不得用"同一机器人不同参数"冒充跨本体；
- 允许的、明确标注的替代研究：**参数敏感性实验**（同本体，变 motion profile / reach 限制），
  只能说明"参数变化下的稳健性"，不能说明跨本体迁移。

## 5. 下一步（按依赖顺序）
1. 选定第二本体（优先 Gazebo 已有模型的成熟机械臂，如 UR5e/Panda）；
2. 只写适配器层（URDF + 控制器桥 + 技能后端参数），不动契约；
3. 跑入口门 1–3，再跑 TransferBench 指标；
4. 若入口门失败，记录失败点，不降低契约或验收标准。
