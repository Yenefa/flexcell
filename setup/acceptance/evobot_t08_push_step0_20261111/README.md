# T08 Push — Step 0 否证探测（归档）

> 代码与原始证据在 `ci-public-window/evidence/evobot_t08_push_step0_20261111/`，
> **该目录不被任何 git 仓库跟踪**。报告本体复制进受跟踪目录以保住结论；证据与脚本仍在原处。

## Lead 独立复核（不采信转述）

从 `run3_z0030/push_step0_summary.json` 自行重算：

| 量 | 我的计算 | t08-push 报告 | 一致 |
| --- | --- | --- | --- |
| 位移 | `hypot(0.22-0.197057, 0-(-0.001924))` = **23.02 mm** | 23.0 mm | ✅ |
| 方向余弦（对 −x） | 0.022943/0.023023 = **0.9965** | 0.9965 | ✅ |
| 侧向 | 1.92 mm | 1.9 mm | ✅ |
| Δz | 0.0 mm | 0.0 mm | ✅ |
| 是否过 30 mm 门槛 | **否** | 否 | ✅ |

## Lead 的裁断

1. **接受 NOT_FEASIBLE 裁定，且接受它拒绝把 30 mm 改成 25 mm。**
   判据在跑之前写死在 `PREREGISTRATION.md`，事后放宽就变成「为制造成功而改判据」。
2. **但必须连读它的解释**：真正被否决的是**方案里那个接触高度做法**，不是「推动」这个方向。
   run2 的 0.0 mm 是**假阴性**（手指在盒顶上方 146 mm，全程没接触），t08-push 主动把它标成
   「不算证据」而不是当成失败结果 —— 这是正确做法。
3. **真正的正面发现**：把高度改对后，方块沿 −x 走了 23.0 mm、方向余弦 0.9965、
   几乎零侧向零 Δz、**全程 `carry.engaged=False`**。这是本栈**第一次**实测到「接触能沿指定方向
   推动且没被夹爪夹走」。
4. **失败点在 23 mm 处饱和**，末端又多走了 16 mm 而方块不动 → **接触丢失**，不是「推得慢」
   也不是「差一点参数」。所以继续调参是错的方向。
5. **等级接受 Simulation Tested（单次探测，n=1）**，不接受 Independently Verified，不接受任何成功率声称。

## 一个必须记录的几何错误（t08-push 自己查出）

`grasp_dz=0.16` 被当成「指尖在 end_effector_link 下方 160 mm」，但 URDF 里
`end_effector_link` 比指尖**还靠外 44.3 mm**，且本栈 position-only IK 会让末端「横着伸过去」。
净效果：手指实际停在盒顶上方 **146 mm**。三种接近路径的指尖高度差 <1.1 mm，**排除路径依赖**。

这是**方案书的错**，不是执行者的错；但它差点被读成「推动不可行」。

## 对后续 T08 的判断

若继续做 T08，正确下一步不是调参，而是：
1. 用本卡给出的网格实测（`gripper_left_palm.stl +0.065m / ±0.029m`）量出夹爪碰撞几何相对
   `end_effector_link` 的偏移；
2. 把 `contact_height_m` 做成**运行时可声明参数**而非常数；
3. 加开环 overdrive，用 `position_error_m` 当「够不到」的诚实信号。

否则任何 push 技能都会重复 run2 那种假阴性。

---

## 以下是 t08-push 原始报告全文

---

# T08 Step 0 — 推动否证探测（跑完了）

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-11 |
| 执行者 | t08-push（teammate） |
| 任务 | T08 推动的 Step 0：**一次运行否证**「接触能把方块沿 −x 推开 ≥30 mm」 |
| 新原语 | **否**（只用 `/move_to_pose` + `capture_ground_truth`） |
| 调用夹爪 | **否**（`GripperClient` 在探测脚本里从未被构造，自检断言） |
| 改验收器/阈值 | **否** |
| LLM 调用 | **0** |
| git commit/push | **无** |
| profile | `sim_profile.profile(out, "velocity_servo", False, "legacy", 0.0, None)`，与 `run_batch.sh:83` 逐字相同 |
| 等级 | **Simulation Tested（单次探测）**；不宣称 Independently Verified |

---

## 0. 裁定

> **NOT_FEASIBLE** —— 按动手前冻结的判据（`PREREGISTRATION.md`）。
> **但"不成立"的原因是几何前提错了，不是"推动物理上不行"。** 这一点必须连读，否则会误判 T08。

| 运行 | 指令 z | box_a 位移 | 方向余弦 | 侧向 | Δz | carry | 裁定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| run2（方案原值） | 0.1775 | **0.0 mm** | 未定义 | 0 | 0 | False | NOT_FEASIBLE |
| run3（修正高度，一次重测） | 0.0300 | **23.0 mm** | **0.9965** | 1.9 mm | 0.0 mm | False | **NOT_FEASIBLE**（<30 mm 门槛 + 非单调） |

**关键解释**：run2 的 0.0 mm **不是**推动失败的证据。那一次里，夹爪手指在盒子顶面上方 **145 mm**，
从头到尾没有接触过盒子——所以「盒子没动」什么也没证明。真正说明问题的是 run3：
把末端降到实测得出的高度后，**方块确实沿 −x 走了 23.0 mm，方向余弦 0.9965，几乎零侧向、零 Δz、
全程未被 carry 夹住**。它卡在 30 mm 门槛前，并且**不单调**。

因此 T08 的真实状态是：**「接触能沿指定方向推动」成立；「推够 30 mm 且单调可控」不成立。**

---

## 1. 为什么 run2 的 0.0 mm 不能当结论

run2 严格按方案执行：P0..P3 四步（x=0.265/0.250/0.240/0.228，z=0.1775），10 步 move_to_pose
全部 SUCCEEDED（`position_error_m ≤ 0.0083`），然后追加 C1..C5 推到 x=0.188。结果 box_a 一动不动。

这个结果太"干净"了，所以我先去查手指到底在哪（`linkdump/`，TF 直接读，不是推断）：

| 量 | 实测 |
| --- | --- |
| 末端 `end_effector_link` z | 0.1810 |
| `gripper_left_link` 原点 | (0.1490, 0.0238, 0.1810) |
| 盒子顶面 | 0.0350 |
| 手指关节原点高于盒顶 | **0.1460 m** |
| 指尖（+0.065 m 网格长轴）高于盒顶 | **0.1409 m** |

**根因**：`grasp_dz_m = 0.16`（`config/week1.yaml:34`）被方案当成「指尖在末端下方 160 mm」。
但 URDF 的实际链条是：`end_effector_link` 在 link5 的 **+0.126 m** 处，手指关节在 **+0.0817 m** 处
（`open_manipulator_x_arm.urdf.xacro:182-260`）——**末端点比指尖还靠外 44.3 mm**。
再叠上这个栈是 **position-only IK**（`move_to_pose.yaml:36` `enforce_orientation: false`），
机械臂用「横着伸过去」的构型到达 z=0.1775，手指根本不是朝下，自然也就没有"挂在下面 160 mm"这回事。

这条与 `t08_minimal_plan.md` §4 的 **U1/U2 完全吻合**：方案自己就写明 U1 是 UNKNOWN，
并说「J2 失败 ⇒ 接触面不在 0.1775，回到 U1 量夹爪碰撞几何，改 `contact_height_m` 再测一次」。
run2 正是这个分支。所以我按方案允许的**一次**重测，而不是就此收工。

另外确认过**这不是路径导致的**（`approachcompare/`）：横着进、先升到 hover 再垂直下降、
先下降再横移——三条路径到同一 XYZ，指尖高度差 <1.1 mm（0.1457 / 0.1468 / 0.1458 m）。
所以是**构型本身**，不是接近方式。

---

## 2. 修正高度是怎么来的（不是试出来的）

`fingersweep/` 扫了 6 个 z，每个位姿读 TF 后算指尖：

| 指令 z | 指尖 z | 指尖高于盒顶 |
| --- | --- | --- |
| 0.1775 | 0.1759 / 0.1800 / 0.1838 | +0.141 ~ +0.149 |
| 0.1000 | 0.0845 | +0.0495 |
| 0.0500 | 0.0347 | **−0.0003** |
| 0.0175 | 0.0057 | −0.0293 |

最小二乘：`tip_z = 1.1126·EE_z − 0.0190`。要让指尖落在盒子上半高度（0.0263），EE_z ≈ **0.0408**。
取 **z = 0.030**（指尖 ≈ 0.0144，位于盒子 0~0.035 的中部偏下），这是**算出来的**，不是扫参扫到的。
网格证据：`geometry/gripper_geometry.json`（`gripper_left_palm.stl` 在自身系里 +0.065 m / ±0.029 m）。

---

## 3. run3 的完整数字（这是本卡唯一的实测推动）

序列与 run2 相同（P0..C5 + retreat），只把指令 z 从 0.1775 改成 0.030。

| 步 | EE x（TF 实测） | box_a x | 累计位移 |
| --- | --- | --- | --- |
| t0_pre | 0.2860 | 0.22000 | 0 |
| P0 | 0.2661 | 0.21794 | 2.1 mm |
| P1 | 0.2428 | 0.20123 | **18.8 mm** |
| P2 | 0.2408 | 0.20261 | 17.5 mm ← **回退 1.3 mm** |
| P3 | 0.2290 | 0.20101 | 19.4 mm |
| C1 | 0.2196 | 0.19898 | 21.1 mm |
| C2 | 0.2162 | 0.19778 | 22.2 mm |
| C3 | 0.2068 | 0.19706 | 23.0 mm |
| C4 | 0.2001 | 0.19706 | 23.0 mm |
| C5 | 0.1910 | 0.19706 | 23.0 mm |
| retreat | 0.2507 | 0.19706 | 23.0 mm（**撤手后零漂移**） |

判据逐条（`run3_z0030/push_step0_summary.json` → `checks`）：

| 判据 | 结果 | 值 |
| --- | --- | --- |
| J1a 至少 3 步到位 | ✅ | 10 步 SUCCEEDED，pos_err ≤ 0.0083 |
| J1b 至少 1 步到接触边界 | ✅ | P2/P3/C1-C5 共 7 步 |
| J7 接触高度 IK 可达 | ✅ | 0 次 `ERR_IK_UNREACHABLE` |
| **J3 单调** | ❌ | P1→P2 回退 1.28 mm |
| **C1 位移 ≥30 mm** | ❌ | **23.0 mm** |
| C2 方向余弦 ≥0.9 | ✅ | **0.9965** |
| C3 侧向 ≤20 mm | ✅ | 1.9 mm |
| C4 Δz ≤20 mm | ✅ | **0.0 mm** |
| C5 carry 全程未 engaged | ✅ | 12/12 采样 `engaged=False, object_id=''` |

**读法**：方向、侧向、离地、未被夹走——四条全过，而且过得很干净（cos 0.9965 几乎完美）。
失败的两条是**幅度**和**单调性**。位移在 C3 之后就**饱和**了：末端从 0.207 继续推到 0.191
（16 mm 行程），方块纹丝不动。这说明**接触在 ≈23 mm 处丢失**，不是"推得慢"。
同时 P1→P2 有一次 1.28 mm 的回退，说明推动过程中方块姿态在变、接触点在滑。

这不是"能推但需要调参"，而是**接触在 23 mm 处不可维持**——正好是 T08 要的"受控推动"缺的那一环。

---

## 4. 这对 T08 意味着什么（给 lead 的判断依据）

1. **否决的是方案里那个具体做法，不是"推动"这个方向。** 方案 §1.2 的接触高度 z=0.1775
   建立在 `grasp_dz=0.16` 的误读上；实测该高度下手指离盒子 145 mm。任何照抄这个 z 的实现
   都会得到"盒子没动"，而那是**假阴性**。
2. **推动本身是可能的**：run3 证明末端确实能把方块沿 −x 推出 23 mm、方向 cos 0.9965、
   Δz = 0、carry 未介入、撤手后不漂。这在证据阶梯上是**第一次**测到「接触 → 定向位移」。
3. **但"受控推动 ≥30 mm"不成立**：接触在 23 mm 处丢失且不单调。按本卡动手前写死的判据，
   裁定必须是 **NOT_FEASIBLE**，不许在看到数据后把 30 mm 改成 25 mm。
4. **若要继续**，正确的下一步不是调参硬凑，而是：先做 §2.3 的 overdrive 设计（把目标位姿设在
   盒子原远侧面之外 20 mm，用 `position_error_m` 当"够不到"的诚实信号），
   并把 `contact_height_m` 作为**运行时可声明参数**而不是常数；同时必须先解决 U1
   （夹爪碰撞几何相对 `end_effector_link` 的偏移），否则任何 push 技能都会重复 run2 的假阴性。

---

## 5. 我明确不宣称什么

- **不宣称** "T08 永远不可行"。run3 显示定向推动真实存在。
- **不宣称** "推动已实现"。位移 23 mm < 30 mm，且不单调，按冻结判据是失败。
- **不宣称** 任何成功率/重复性：n=1，单次探测，**Simulation Tested**，不是 Independently Verified。
- **不宣称** `grasp_dz=0.16` 在**拾取**语境下是错的——本卡只证明它在"低姿接触/推动"语境下
  不能当作"指尖在末端下 160 mm"来用。
- **不宣称** 23 mm 是物理上限；只宣称**本构型、本高度、本路径下**接触在 23 mm 处丢失。

---

## 6. 文件

| 路径 | 内容 |
| --- | --- |
| `PREREGISTRATION.md` | **跑之前**写死的判据（本卡纪律的物证） |
| `run2/` | 方案原高度 z=0.1775 的完整运行（12 次真值采样、轨迹 jsonl、summary） |
| `run2/push_step0_summary.json` | run2 裁定与逐条 checks |
| `run2/push_step0_trajectory.jsonl` | 每步：GT、EE、carry、夹爪关节角 |
| `run2/sim/skills/move_to_pose.jsonl` | 技能服务器的自述日志（outcome/pos_err/reached_pose） |
| `run3_z0030/` | **修正高度 z=0.030 的实测推动**（本卡主结果） |
| `run3_z0030/push_step0_summary.json` | 23.0 mm / cos 0.9965 / 非单调 |
| `linkdump/link_poses.json` | 证明手指在盒顶上方 146 mm 的 TF 现场 |
| `fingersweep/finger_sweep.json` | 6 个 z 的指尖高度，用于拟合修正高度 |
| `approachcompare/approach_compare.json` | 三条接近路径 → 指尖高度不变（排除路径依赖） |
| `geometry/gripper_geometry.json` | 碰撞网格实测尺寸 + URDF 关节偏移（U1 的答案） |
| `run1/` | 第一次尝试，探测脚本 `vec()` 读 GT 格式的 bug，**作废**（保留以示未删） |

## 7. 复现

```bash
# 判据逻辑自检（不需要仿真，11 个用例）
wsl -d Ubuntu-24.04 -- bash -c 'source /opt/ros/jazzy/setup.bash && source /home/ros/flexcell-p14-ws/install/setup.bash &&   python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_t08_push_step0_selftest.py'

# 实跑（先确认仿真通道空：pgrep -f 'gz sim' 无输出）
EVOBOT_ROS_DOMAIN=120 bash ci-public-window/scripts/evobot_t08_push_step0_run.sh <out> --z 0.030
```

脚本：`ci-public-window/scripts/evobot_t08_push_step0_probe.py`（探测）、
`evobot_t08_push_step0_run.sh`（起栈/teardown）、`evobot_t08_push_step0_selftest.py`（判据自检）、
`evobot_t08_finger_sweep.py` / `evobot_t08_approach_compare.py` / `evobot_t08_link_pose_dump.py` /
`evobot_t08_gripper_geometry.py`（诊断）。
