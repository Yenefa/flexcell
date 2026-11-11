# T08 推动：最小可验证实现方案

> 状态：**方案（Designed）**。没有一行 push 代码存在，也没有跑过任何一次推动。
> 本文的每个数字要么来自仓库里的 file:line，要么标成 UNKNOWN。
> 母文档见 `README.md`；本文件只回答「怎么用最小代价知道行不行」。

---

## 0. 一句话

**不需要新运动原语。** `move_to_pose` 已经是「把末端挪到某个位姿」的通路，
它不碰夹爪（`action/MoveToPose.action:12-31`、`move_to_pose_server.py:1034-1091`）。
T08 要加的是三样**外围**东西：一条**动作通路**、一条**位移判据**、一个**接触前/后的真值对比**。
所以顺序是「先花一次运行否证，再写代码」，而不是「先写一个 push 原语」。

---

## 1. Step 0 —— 一次运行，把最关键的那个未知问掉

### 1.1 要问的问题

> 把末端降到 z = 0.1775（= 盒心 0.0175 + `grasp_dz` 0.16，`config/week1.yaml:34`），
> 沿 −x 分三步逼近 box_a，**盒子会不会被推开**？

为什么这个问题值一次运行：

| 已有证据 | 它证明了什么 | 它没证明什么 |
| --- | --- | --- |
| `pick_server.py:468-472`（实测 2026-09-26） | 盲接近会**把方块扫到一边**，落点差 4.7 cm | 方向、幅度、可重复性 |
| `pick_server.py:180-186`（实测 2026-11-04） | 一次 carry 把第三个盒子**撞飞 0.18 m** | 同上；且这是「不需要的」碰撞 |
| `docs/HANDOFF.md:345` | 低位失控朝向扫进方块/地面，**实测差 4–7 cm** | 未受控，没有可控性结论 |
| `docs/SIGNED_CONTACT_FORCE_20261031.md:58` | 静置盒子接触力已签名校准 | **明确排除机械臂**：no arm, no attachment, no grasp |

结论：**「末端会跟方块发生接触」是实测过的；「接触能把方块沿指定方向推走指定距离」没有。**
Step 0 就是把这后半句第一次量出来。如果它不成立，T08 直接判 NOT_FEASIBLE，
省掉后面全部开发——这就是「先做 T08」的真正理由。

### 1.2 怎么做（不写新原语）

- profile 用与批次**逐字相同**的一次调用：`sim_profile.profile(out, "velocity_servo", False, "legacy", 0.0, None)`
  （`setup/acceptance/evobot_unified_runner_20261111/run_batch.sh:83`），
  这样结论对现有批次有效，不是对某个特制世界有效。
- 起栈后 planning scene 里**没有盒子**：只有技能会 `add_box`
  （`common.py:544-557`；调用点 `pick_server.py:196,471`、`place_server.py:412,453`），
  所以规划器会**直接朝接触位姿走**，不需要任何场景手术。
  ⚠️ 例外：本轮若先跑过 PICK，`pick_server.py:438` 会把**全部**盒子同步进场景，
  那时必须先 `remove()` 目标盒子（`common.py:589-604`），否则规划器绕开它、永不接触。
- 每步动作 = 一次 `/move_to_pose`（`common.MoveToPoseClient`，`common.py:381-435`），
  **不调用夹爪**（保持闭位姿：`config/week1.yaml:32` `gripper_close_position=-0.011`，
  避免张开的两指把盒子夹在中间）。
- 每步前后各采一次真值：`benchmark/evaluators/capture_ground_truth.py:26-37`
  （走 gz `Pose_V`，与技能服务器同一个 `sample_gz_pose`，不是第二个真相来源）。

三个位姿（world 帧，z 固定 0.1775，y 固定 0）：

| 步 | EE 目标 (x, y, z) | 与 box_a 中心(0.220)的关系 |
| --- | --- | --- |
| P0 | (0.265, 0, 0.1775) | 距盒心 45 mm，盒半径 17.5 mm → **离面 27.5 mm**，应无接触 |
| P1 | (0.250, 0, 0.1775) | 离面 12.5 mm，仍应无接触 |
| P2 | (0.240, 0, 0.1775) | 离面 2.5 mm，**接触边界** |
| P3 | (0.228, 0, 0.1775) | 越过近侧面 9.5 mm → 必须发生位移，否则说明接触面不在这个高度 |

（包络校验：P0 的 `sqrt(0.265² + 0 + (0.1775−0.02)²) = 0.3084 ≤ 0.35`，
公式 `docs/HANDOFF.md:345`，实算见 `verify.py` F1。）

### 1.3 Step 0 的判据（全部是「物体位移」，没有一条是「机器人动了」）

| # | 判据 | 阈值 | 依据 |
| --- | --- | --- | --- |
| J1 | 动作真的执行了 | P0..P3 至少 3 个 SUCCEEDED 且 `position_error_m ≤ 0.02` | `move_to_pose_server.py:109,785-796` |
| J2 | 接触**发生** | P0→P1 的 box_a 位移 ≤ 0.005 m（无接触）；P2→P3 位移 ≥ 0.010 m | 分解「接触前安静」和「接触后动了」两段 |
| J3 | 位移是**单调**的 | 每推进 12 mm，累计位移非减 | 排除「先撞飞再回弹」 |
| J4 | 方向对 | 位移向量与 −x 的余弦 ≥ 0.9 | 排除侧向甩出 |
| J5 | 不飞 | 终态 Δz 绝对值 ≤ 0.02 m，|Δy| ≤ 0.02 m | `evaluate.py:22` 的静置高度阈值 |
| J6 | 不是被搬走 | 全程 `carry.engaged == False` 且 `object_id == ''` | `contracts/composite.py:96` |
| J7 | 机器人**够得着**接触位姿 | P2/P3 的 IK 预检不返回 `NO_IK_SOLUTION` | `move_to_pose_server.py:1142-1170` |

**J2/J7 是生死判据**：J7 失败 ⇒ 这个高度够不着（T08 判 NOT_FEASIBLE，或改用更浅的接触高度）；
J2 失败但 J7 通过 ⇒ 接触面不在 0.1775（回到 U1，量夹爪碰撞几何）。

### 1.4 成本与产物

1 个约 60 行的探测脚本（probe，不是原语）+ 1 次 Gazebo 运行 + 1 份 raw json。
判据全部离线可复核（`capture_ground_truth` 的 xyz 四舍五入到 1e-6，够 1 mm 判读）。

---

## 2. Step 1 —— `PushObject` 动作（Step 0 通过后才做）

### 2.1 接口

```
# action/PushObject.action
string request_id
string object_name                 # 必须在 tracked_objects 里
geometry_msgs/Vector3 direction    # 世界帧单位向量，z 必须为 0
float64 distance_m                 # 0.03 .. 0.15
float64 contact_height_m           # 接触高度（默认 = 物体初值 z）
string motion_profile_id
uint32 deadline_ms
---
uint8 OUTCOME_SUCCEEDED=0
uint8 OUTCOME_FAILED=1
uint8 OUTCOME_CANCELED=2
uint8 OUTCOME_STATE_UNKNOWN=3
uint16 ERR_INVALID_GOAL / ERR_NOT_REACHABLE / ERR_CONTACT_NOT_MADE /
       ERR_DISPLACEMENT_SHORT / ERR_DISPLACEMENT_OFF_AXIS /
       ERR_OBJECT_LEFT_TABLE / ERR_MOTION_FAILED / ERR_CARRY_ENGAGED ...
float64 measured_displacement_m    # gz 真值
float64 direction_cos              # 与请求方向的余弦
float64 lateral_m                  # 垂直方向的偏移
bool    arm_reached_target         # move_to_pose 的 SUCCEEDED
bool    carry_engaged_during
geometry_msgs/Pose measured_before / measured_after
string evidence_id
```

### 2.2 五个相位（照 `place_server.py` 的骨架，不发明新结构）

| 相位 | 做什么 | 拒绝条件（全部 typed，不猜） |
| --- | --- | --- |
| VALIDATING | 单位向量 / 距离区间 / 包络 `sqrt(x²+y²+(z−0.02)²) ≤ 0.35` / 物体在 tracked_objects / **物体未被搬运**（`is_attached`，`common.py:606-625`）/ `carry.engaged == False` | 任一不满足 → 立刻失败，不动 |
| APPROACH | `move_to_pose` 到**接触前**位姿（沿 −direction 退回 `distance+` 净空） | EE 没到 → ERR_NOT_REACHABLE |
| **PRECHECK** | 采一次真值，必须与调用方声明的初值 ≤ 0.015 m | 否则 ERR_OBJECT_ALREADY_MOVED（**这一步堵住「接近时先撞跑了再推」**） |
| PUSH | 一次 `move_to_pose` 到 `接触位姿 + direction × (distance + overdrive)`，overdrive = 0.02 m | EE 没到 → ERR_CONTACT_NOT_MADE（物体没让步）；到了但位移不足 → ERR_DISPLACEMENT_SHORT |
| VERIFY | 采真值，算 displacement / direction_cos / lateral / Δz | 越界 → 对应 ERR_* |
| RETREAT | `move_to_pose` 退回 | 只影响报告，不改判定 |

**唯一与现有技能相反的约定**：**不**把目标盒子加进 planning scene。
现有所有技能都加（`pick_server.py:471`，注释写明是为了让接近路径**绕开**它）；
推动必须反过来，否则规划器会把「进入盒子」判为碰撞并绕过去——**永远不接触**。
这一条要写进代码注释，否则下一个人会「顺手修好」它。

### 2.3 为什么 overdrive 是必须的

如果目标位姿正好停在盒子**原来**的远侧面，两种世界状态看起来一样：
（a）盒子被推动了、EE 到了；（b）盒子没动、EE 卡在盒面上但也「勉强」在容差内。
令目标 = 接触位姿 + direction × distance + 0.02 m overdrive：
- 盒子让步 ⇒ EE 能走到（位移 ~ distance）；
- 盒子不让步 ⇒ EE 停在盒面上，`position_error_m` ≈ 0.02+ ⇒ `ERR_POSE_NOT_REACHED`。
**「够不到」本身就是一个诚实信号**，这是 `move_to_pose` 自带的实测门
（`move_to_pose_server.py:786-796`），不是我们另加的。

---

## 3. 如何验证「真的推动了，而不是夹爪夹着走」

这是 lead 明确要求的判据设计。**七个信号，全部要求，缺一即失败。**
关键点：**没有一条来自技能的自述**——技能说 SUCCEEDED 不算数
（`evaluate.py:5-8` 的契约：evaluator 只读观测，不读任何 agent 写的字）。

| # | 信号 | 为什么这条能挡住它 | 出处 |
| --- | --- | --- | --- |
| S1 | 位移由 **gz Pose_V 真值**测，前后各一次，`max_age_s=0.5` | 「夹着走」与「推着走」在真值里都是位移，所以 S1 只负责**证明动过**，不负责分类 | `capture_ground_truth.py:26-37`；`place_server.py:361,442` 的采样用法 |
| S2 | `carry.engaged == False 且 object_id == ''`（推前、推后各一次） | 本栈**没有接触抓取**：承载是位姿伺服（`CarryDynamics.cc:1`），一旦 engaged 物体就是被钉在 EE 上。这条把「夹着走」变成类型化失败 | `contracts/composite.py:96` 已把这条当硬前提 |
| S3 | 动作期间**从未调用** `/gripper_controller/gripper_cmd`（技能自证 + 日志可查） | 夹爪行程只有 0.031 m（`0.02 → −0.011`，`config/week1.yaml:31-32`），放不进 0.035 m 的盒子；真正有多少指间净空属 U1/UNKNOWN。不调用夹爪就没有「夹」这个解释 | `common.py:436-518` |
| S4 | EE **确实到达**了 overdrive 目标（`position_error_m ≤ 0.02`） | 挡「机器人没走到、物体自己滑了」以及「机器人卡死但报成功」 | `move_to_pose_server.py:786-796` |
| S5 | 位移方向余弦 ≥ 0.9，侧向 ≤ 0.02 m | 挡「推歪/甩出去」 | Step 2 新子句 |
| S6 | 终态静置高度 `abs(z − 0.0175) ≤ 0.02` | 挡「推飞/翻倒」；阈值直接沿用验收器已有的 REST_HEIGHT_TOLERANCE_M | `evaluate.py:22` |
| S7 | 位移有**上界** 0.15 m | 挡「一把推到桌子另一头」，那不是受控推动 | Step 2 新子句 |

**位移下限 X = 30 mm**：`box_follow_min_m = 0.03`（`config/week1.yaml:40`，仓库自己的
「物体真的跟着动了」阈值）；同时是「没动」带宽 0.015（`evaluate.py:23`）的 2 倍；
且 ≈ 0.86 个盒宽（`worlds/flexcell_world.sdf:105`），不会与抖动混淆。

---

## 4. 如何防止「把物体推飞也算成功」

验收器现在**只能**看终态（`evaluate.py:42`），所以「推飞」只能靠**终态的几何+运动学**封堵。
逐条对着假成功路径写：

| 假成功 | 封堵 | 现状 |
| --- | --- | --- |
| 推飞/甩出去 | S5 + S6 + S7 | 需要新子句 |
| 翻倒/滚走 | S6（静置高度）+ 上界 | 需要新子句 |
| 夹着走 | S2 + S3 | **已有**（`composite.py:96`） |
| 没动但报成功 | 位移由真值测（S1），技能 outcome 不参与评分 | **已有**（`observe_from_run.py:1-18,85-94`） |
| 接近时先撞跑，再「推」已到位的东西 | PRECHECK（≤ 0.015 m） | 需要新相位 + 新子句参数 |
| 两次动作累加位移 | 只从 spec 声明的 `initial_pose` 量（`generate.py:69-70`） | **已有**（用 spec 的初值而不是运行时快照） |
| 用过期的观测 | 采样 `max_age_s = 0.5` | **已有**（`place_server.py:361,442`） |
| 同一目标被重复计数 | 每任务单次声明的推动距离 | 生成器侧约束 |

注意：`docs/HANDOFF.md:342` 已经记录本栈把「**夹爪扫飞方块**」当成**假成功**拦截过 4 次。
T08 的判据设计必须保证：**扫飞在新任务里是失败，不是通过**——上面 S5/S6/S7 就是这个保证。

---

## 5. Step 2 —— 评分侧（走冻结流程，不偷改尺子）

1. `benchmark/evaluators/evaluate.py` 新增 `push:<obj>` 子句，**只增不减**
   （先例：`evaluate.py:111-119` 的 `visit_sequence`、`:132-142` 的 `relative`，
   两处注释都写明 new clause / only ADD），版本号从 0.2.0 起升。
2. 登记 `docs/FREEZE_CHANGELOG.md`（流程见其 :1-42；`docs/AGENT_HANDOFF.md:295,367` 要求）。
3. 新增回归测试，证明既有 64 条归档运行的评分**逐条不变**（先例：
   `evobot_skill_growth_20261111/README.md:14-22` 记录了一次完整的新增条款流程与 64/64 回归；
   `benchmark/tests/test_claim_does_not_affect_grading.py` 是「新字段不影响评分」的测试范式）。
4. 生成器新增 `T08_push`，把 `NOT_IMPLEMENTED`（`generate.py:53-58`）里那一条删掉——
   但**只有在 Step 0/1 都通过之后**。在那之前，继续拒绝是对的。

---

## 6. 顺序与终止条件（写给下一个执行者）

```
Step 0  一次探测
   ├─ J7 失败 (IK 够不着)            → T08 = NOT_FEASIBLE，记录并停手
   ├─ J2 失败 (接触高度不对)         → 量夹爪碰撞几何(U1)，改 contact_height_m 再测一次
   ├─ J3/J4 失败 (方向/单调不成立)   → T08 = NOT_FEASIBLE（不可控），记录并停手
   └─ 全过                            → Step 1
Step 1  PushObject 动作 + push_server
   └─ 连续 N 次里位移达标率 < 阈值     → 记录为「能推但不可靠」，先不生成任务
Step 2  push 子句 + T08 模板 + 冻结登记
```

**明确的终止条件**比「再调调看」重要：本仓库已经出过一次
「为了让批次好看而放宽阈值」被写进纪律禁止的先例
（`docs/MECHANISM_20261001.md:181`：不能靠降阈值/延长等待抹平失败）。
Step 0 的判据是**动手前**写死的，不允许在看到数据后再改。

---

## 7. 这份方案明确不做的事

- 不新增运动原语、不新增物理插件、不改世界文件（`worlds/*.sdf`）、不改 `sim_profile` 的 scene 白名单。
- 不改 `move_to_pose` 的容差、不改 `composite` 的 clearance 下限。
- 不在 Step 0 通过之前写 `push_server.py`（先写会得到一个没有判据的「能动就算赢」的技能，
  正是 mission 要避免的东西）。
- 不声称任何 rung：本文件是 Designed，连 Implemented 都不是。
