# T08 轨迹证据验证器：架构与源码审计（交付物 1）

**审计目的：在写任何新代码之前，先确定现有物理遥测能复用多少。**
结论：**大部分证据通道已经存在**，缺的是统一 schema、完整性校验和 fail-closed 判定。

---

## 1. 已存在的物理遥测（可直接复用）

### 1.1 `PhysicsTrace` —— 逐步物理日志

```
源码  src/flexcell/flexcell_gazebo/src/PhysicsTrace.cc
发布  /flexcell/physics_trace  (gz.msgs.StringMsg)
配置  sim_profile.py:193   <plugin name='flexcell::PhysicsTrace'>
```

- 每步写 `stepLog`，精度 `std::setprecision(15)`
- 通过 `parameter_bridge` 桥到 ROS（`/flexcell/physics_trace@std_msgs/msg/String`）
- `carry_server.py:117` 已在订阅它 → **carry 状态通道现成**

### 1.2 `ContactTrace` —— 接触快照（**这是支撑接触与推杆接触的证据源**）

```
源码  src/flexcell/flexcell_gazebo/src/ContactTrace.cc
配置  sim_profile.py:207   <plugin name='flexcell::ContactTrace'>
```

源码头两行的自我约束已经是对的：

> Read-only snapshots of Gazebo's contact components; never creates a sensor,
> moves a body, or **treats silence on a contact topic as an empty contact set**.

关键能力（读代码确认）：

| 能力 | 证据 |
| --- | --- |
| 按模型名监视碰撞体 | `watches` 列表，1–16 个，重名直接抛错 |
| 逐步记录接触数据 | 每步写 `contacts`（protobuf→JSON） |
| **区分「没有接触」与「组件不存在」** | 写 `component_present: true/false`，不存在时 `contacts: null` |
| 强制要求日志路径 | 未给 `new contact step log path` 直接抛错 |

**最后两条正是 fail-closed 需要的语义**：沉默不能当空集。

### 1.3 位姿采样

```
flexcell_skills/common.py    sample_gz_pose / sample_gz_pose_age
ci-public-window/scripts/evobot_z_tracker.py   密集 z 采样（已实测）
```

实测数据（T08 首推，2026-11-12）：

```
5988 样本，achieved_hz 19.901，2994 样本/物体，最大间隙 0.561 s
max_lift_above_rest_m = 0.00226
```

`trajectory.json` 已带 `limit` 字段自报局限：
「稀疏采样只能低报 max_z，会把搬运误判成推」。

### 1.4 夹爪与 carry 状态

| 通道 | 位置 |
| --- | --- |
| `/joint_states` | 已发布；`move_to_pose.yaml:16`、`week1.yaml:10` 均指向它 |
| `RobotStateSummary.msg` | 有 `gripper_joint_name` 字段，注释写明「first gripper* joint seen in /joint_states」 |
| carry 状态 | `carry_server.py` 的 `carry_state_topic` / `carry_snapshot` / `carry_query_service` |
| PushObject 结果 | 已有 `carry_engaged_during` 布尔字段 |

**实测佐证**：T08 首推报 `carry_engaged_during = false`，同刻轨迹 `max_lift = 2.26 mm`，
两条独立证据一致指向「没有抓取」。

---

## 2. 明确缺失的（必须新建）

| 缺失 | 为什么必须有 |
| --- | --- |
| **统一轨迹 schema** | 现在 z 采样、contact log、physics trace 三者格式各异，无法联合判定 |
| **证据完整性校验** | 无 task_id / run_id / 时间窗 / 单调序列 / 间隙上限 / 丢弃计数 |
| **SHA-256 清单** | 归档证据可被事后静默修改 |
| **推杆 link 显式身份** | `ContactTrace` 按模型名监视，但没有指定「哪个 link 是推杆」 |
| **teleport 检测** | 模型被外部直接改位姿时，轨迹看起来和推一样 |
| **支撑接触** | 有 contact 原始数据，但没有「物体始终被桌面支撑」的判据 |

---

## 3. 设计约束（来自 mission，逐条）

| 约束 | 落地方式 |
| --- | --- |
| 保留 v0.3.0 | 不删改；新验证器单独版本号 |
| 不静默改 30 mm | 阈值原样；新检查只加不减 |
| 不把视觉模型当主判据 | 视觉只做诊断；物理证据来自 gz 遥测 |
| 不改 PushObject 实现 | 只读其结果字段 |
| 不改 TaskSpec | 冻结 |
| 隔离工作区 | `/tmp` overlay，不碰在用 install |
| 不基于合成测试宣称 Level 4 | 报告必须分四层写 |

---

## 4. 一条已经验证过的反面证据（说明为什么必须做）

`evaluate.py` v0.3.0 只看终态时：

```
同一输入 (0.22,0,0.0175) -> (0.16,0,0.0175)
v0.3.0 passed = True     ← 「抓起来搬过去放下」也会通过
v0.4.0 passed = False    ← 加入轨迹要求后 fail closed
```

v0.4.0 是**最小**修补（只查 max_z）。本任务要求的是**完整**证据：
支撑接触、推杆接触、夹爪状态、teleport 检测，缺一即判 false。

---

## 5. 复用判断小结

| 需求通道 | 状态 | 来源 |
| --- | --- | --- |
| 物体轨迹 XYZ+朝向 | **已有** | `sample_gz_pose` / z_tracker（需扩到全 6 自由度） |
| 时间戳单调 | **部分** | gz 仿真时间可用；需记录序列号与间隙 |
| 支撑接触 | **数据已有，判据没有** | `ContactTrace` |
| 推杆接触 | **数据已有，身份没有** | `ContactTrace` + 需指定 push link |
| 夹爪关节状态 | **已有** | `/joint_states` |
| carry 状态 | **已有** | `carry_server` / `PushObject.carry_engaged_during` |
| teleport 检测 | **没有** | 需新建 |
| SHA-256 清单 | **没有** | 需新建 |

**结论：不需要新建物理传感器，需要新建证据编排与判定层。**
