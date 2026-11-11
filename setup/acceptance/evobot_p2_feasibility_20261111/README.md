# P2 可行性论证：T07–T10 在当前单臂栈上能否实现

> **这是一份评估，不是能力。** 本卡没有让任何机器人动过，也没有新增原语。
> 它回答的是「值不值得做、先做哪个、用什么信号验收」，而不是「已经会了」。

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-11 |
| 执行者 | skill-gap（teammate，task-7） |
| 仓库 | `project-033-flexcell/wt-comp` @ 起点 `4a97c250`、写作期间被并发会话推进到 `b396e340`（见 §6 说明） |
| 范围 | mission §3 Phase 2（T07 堆叠 / T08 推动 / T09 杂乱 / T10 受约束放置）的可实现性 |
| 跑过仿真 | **否**（Gazebo 被 Baseline A 批次占用） |
| 新增原语 | **否**（只给方案，见 `t08_minimal_plan.md`） |
| 改验收器/阈值 | **否** |
| LLM/API 调用 | **0** |
| git commit/push | **无** |

上面「不改验收器」是**这一轮的行为**，不是主张验收器不该改：T08 想被评分，必须
新增一条子句，那要走 `docs/FREEZE_CHANGELOG.md` 的冻结流程（见 §2.6）。

---

## 0. 结论

用户第 3 轮裁决把重心放到 **T08**。四类的裁定：

| 任务 | 裁定 | 一句话理由 |
| --- | --- | --- |
| **T08 推动** | **FEASIBLE_WITH_PRIMITIVE_WORK** | 运动侧**不需要新原语**（`move_to_pose` 本来就是「不闭合夹爪把末端挪到某个位姿」）；缺的是**接触语义 + 位移判据 + 一条动作通路**。接触位移在本栈**已被实测过**（不是推演）。**建议先做这个。** |
| T07 堆叠 | **FEASIBLE_WITH_PRIMITIVE_WORK** | 但阻塞点**不是**「place 不能指定 z」——`place_server.py:278` 明明接受任意 z。真正的硬阻塞是 `composite` 的 `clearance_m` 下限 0.05 m > 堆叠节距 0.035 m，**算术上不可能**通过。评分侧（`min_tiers`）反而**早就写好了、没人用**。 |
| T09 杂乱 | **NOT_FEASIBLE（作为独立能力）** | 世界是 oracle 真值（`composite.py:93`），「在干扰物中识别目标」这一步**根本没被考**。剩下的只是「物体数 3→4/5」= mission `EVOBOT_NORTH_STAR_MISSION.md:134` 明令禁止的凑数包装。 |
| T10 受约束放置 | **NOT_FEASIBLE（在现验收器契约下）** | 场景与执行**都已被实测通过**（`c13` 的 legacy 顶板 PASS 6/6）；但验收器是**终态纯函数**（`evaluate.py:5-8,42`），「怎么到达的」它看不见。同一个终态在自由放置和受约束放置里字节相同 → **不可区分即不可评分**。 |

**先做 T08**，理由不是「它最容易」，而是：它**唯一的致命未知可以用一次现有技能的实验否证**，
不需要写任何新原语（§2.5 Step 0），而且它失败的证据链在本仓库里已经存在
（`pick_server.py:468-472`、`docs/HANDOFF.md:342,345`）。T07 需要先动契约，T09/T10 需要先动研究问题。

---

## 1. 这份论证怎么被检查

```
python3 setup/acceptance/evobot_p2_feasibility_20261111/verify.py
# === 26/26 claims hold ===   (exit 0)
```

`verify.py` 是**只读论证检查器**：不跑仿真、不连 ROS、不联网、不写仓库里的任何源文件。
它把本文每条可计算的断言重新算一遍（结果存 `verify_result.json`）。它检验的是
**契约允许什么/禁止什么**，以及**归档运行已经达到过什么**；它**不能**证明推动在物理上成立。
逐条清单见 `claims.tsv`。

---

## 2. T08 推动（重点）

### 2.1 盘点：「不闭合夹爪、按目标轨迹移动末端」的通路，已经有了

| 事实 | 证据 |
| --- | --- |
| `move_to_pose` 的 goal 只有 4 个字段：`target`(PoseStamped) / `motion_profile_id` / `expected_world_revision` / `deadline_ms`——**没有夹爪字段** | `src/flexcell/flexcell_interfaces/action/MoveToPose.action:12-31` |
| 校验只看 frame 可解析、四元数归一、workspace、profile 白名单、world revision——**不看夹爪状态，不看是否搬运中** | `src/flexcell/flexcell_skills/flexcell_skills/move_to_pose_server.py:1034-1091` |
| 夹爪是**另一个 action**，由 `GripperClient` 单独驱动；不调用它，夹爪就保持不动 | `.../common.py:436-518`、`.../config/week1.yaml:30` |
| 成功判据是**实测末端位姿**入容差（默认 0.02 m），不是 MoveIt 自称成功 | `.../move_to_pose_server.py:109, 785-796` |
| 姿态默认不强制（position-only 求解器），IK 搜索球 8 mm | `.../move_to_pose_server.py:111, 114, 1126-1137` |

**所以「张着夹爪把末端推过去」不需要新原语。** 需要的只是：把目标位姿选在**物体内部**
（越过它的近侧面），让接触发生。这与 `TASK_CATALOG.md:40` 的「nothing currently contacts a box
side; all motion targets are grasp poses」并不矛盾——它说的是**现有的目标位姿**都是抓取位姿，
不是**通路**不存在。这条区别就是 T08 能做而 T07 不能做的原因。

### 2.2 缺的三件东西（都有 file:line）

1. **动作通路**：agent 唯一的动作出口是 `RunComposite`，而一个 stage 只能是
   `{stage_id, object_name, place_pose}`（`.../msg/CompositeStage.msg:1-4`，
   `.../contracts/composite.py:58-64` 用 `set(stage) != {...}` 精确卡死）。
   决策层菜单同样没有 PUSH：`ACTION_OBSERVE/PICK/PLACE/VERIFY/WAIT/ABORT`
   （`.../task_fsm_server.py:893-895`）。
2. **位移判据**：验收器的 goal 词表只有
   `placement / unmoved / order / visit / visit_sequence / min_tiers / relative`
   （`benchmark/evaluators/evaluate.py` 全文；`verify.py` B1）。其中唯一「看物体动没动」的阈值
   `UNMOVED_TOLERANCE_M = 0.015` 是**用来判「不该动」的**（`evaluate.py:23, 71-85`）。
   `verify.py` B3 演示：把物体推动 60 mm，最接近的 `placement` 子句判 **FAIL**；
   B3b 演示：同一个 60 mm，`unmoved` 子句也判 **FAIL**。**今天没有任何子句能给一次成功的推动打分。**
3. **接触语义**：推动要求「不夹住、靠外侧接触施力」。当前所有技能都假设
   「先让 MoveIt **避开**这个盒子」（`pick_server.py:468-472` 的注释：把盒子加进 planning scene
   是为了让接近路径**绕开**它），推的反面。这个假设必须在 push 技能里显式反转，否则
   规划器会把目标位姿判成碰撞并绕过去，**永远不接触**。

### 2.3 接触是真实的；「受控推动」从未被测量

这是 T08 判定的核心，也是最容易被写成猜测的地方，所以逐条给证据：

| 结论 | 证据 |
| --- | --- |
| 盒子是**真物理刚体**（0.05 kg，35 mm，mu=1.0），不是装饰 | `worlds/flexcell_world.sdf:97-113` |
| 承载是**位姿伺服**，不是接触抓取；只有 engaged 时才钉住物体，否则物理拥有它 | `src/flexcell/flexcell_gazebo/src/CarryDynamics.cc:1`（注释原文）、`:162-166` |
| 批次实际用的就是这套（`velocity_servo` + legacy），并非某个只在文档里存在的后端 | `setup/acceptance/evobot_unified_runner_20261111/run_batch.sh:83`、`scripts/sim_profile.py:154` |
| 静置盒子的接触力**被实测并签名**：501 个 2 ms 样本，合力 = m·g = 0.49 N，方向余弦 1.0 | `docs/SIGNED_CONTACT_FORCE_20261031.md:41-49` |
| 但那份证据**明确排除机械臂**：「no arm, no attachment, no grasp」 | `docs/SIGNED_CONTACT_FORCE_20261031.md:58` |
| **机械臂已经扫飞过方块**（不是推断，是当时实测拦截到的假成功） | `docs/HANDOFF.md:342`「本日实测拦截 4 次假成功：**夹爪扫飞方块**、IK 超界、附着失效等」 |
| 更具体：一次「盲接近」把方块**扫到一边**，落点差 4.7 cm | `pick_server.py:468-472`（注释注明实测 2026-09-26） |
| 低位失控朝向时「长夹爪扫进方块/地面，**实测差 4–7 cm**」，所以 EE 安全区是 z ≳ 0.16 | `docs/HANDOFF.md:345` |
| 又一次、更大：只登记抓取目标时「规划器对其余盒子全盲，直接扫穿过去（实测 2026-11-04：**一次 carry 把第三个盒子撞飞 0.18 m**）」 | `pick_server.py:180-186`（docstring 原文） |
| 现有缓解措施是把盒子塞进 planning scene 让机械臂**绕开**（反面） | `pick_server.py:471-474`；绕不开时 `remove()` 后重试一次并显式接受 knock risk，`pick_server.py:489-495` |

**读法（严格）**：本栈**证明了**「末端会与方块发生接触并把方块推开」；**没有证明**
「能把方块沿指定方向推开指定距离并让它停在原地」。
前者是意外，后者才是 T08 要的能力。所以裁定是 FEASIBLE_WITH_PRIMITIVE_WORK，
而 Step 0 的实验就是用来把后者第一次测出来（§2.5）。

> 相邻工作流的旁证，**不是本栈证据**：`setup/acceptance/evobot_tall_bottles_20261111/README.md:87,93`
> 记录了 `push_then_neck`（推一下再抓）在 LIBERO/MuJoCo 上失败、侧向抓取把物体推倒。
> 不同仿真器、不同物体、不同夹爪，**不作为本栈的任何结论**；仅说明「推」这种动作在
> 同类研究里确实廉价可试。

### 2.4 运动学与几何：数值边界

臂展包络（仓库自带的先验公式）：`sqrt(x² + y² + (z − 0.02)²) ≤ 0.35`，`docs/HANDOFF.md:345`。
EE 安全高度 `z ≳ 0.16`（同一条），因为夹爪实体在 EE 下方 160 mm
（`config/week1.yaml:34` `grasp_dz_m=0.16`；`:58` `carry_offset_m=0.16`；
实测 grasp 目标 z = 0.0175 + 0.16 = **0.1775**，见
`setup/acceptance/evobot_t05_n6_20261111/runs/s1000-a1/sim/skills/move_to_pose.jsonl` 的
`target_box_b-grasp` 记录，误差 0.0040 m）。

推论与实算（`verify.py` F1–F3）：

| 量 | 值 | 判定 |
| --- | --- | --- |
| 推 box_a 的接触位姿 (0.26, 0, 0.1775) | 包络 0.3040 ≤ 0.35 | ✅ 在包络内 |
| 推 box_b 沿**自身外径向** 60 mm → (0.2446, −0.2201) | 包络 0.3648 > 0.35 | ❌ **出包络** |
| 堆叠放置的 EE 位姿 (0.22, 0, 0.2245) | 包络 0.3004 ≤ 0.35 | ✅ 在包络内（T07 的阻塞不在臂展） |
| 归档 3133 条 goal 里 EE **实际到达**的最低 z | **0.1717** | ✅ 低于推的接触高度 0.1775 → 该位姿**已经在本栈到达过** |
| 归档里 EE **被命令过**的最低 z | **0.1000**，且 FAILED（`NO_IK_SOLUTION`） | 提示别把 EE 往更低处压 |

**这两条合起来是一个很强的结论**：推的接触位姿 (0.26, 0, 0.1775) 在
(a) 已声明的臂展包络内，(b) 已实测到达过的 z 范围内。所以 **T08 的第一步不需要新运动学**。
同时它给出一个真实的设计约束：**往外推会很快走出包络，往里/横向推才是安全方向**
（verify.py F2）。这不是理论上限，是 0.35 包络与 box_b 位于 r=0.269 共同决定的算术事实。

### 2.5 最小可验证实现：先花一次运行把它否证掉

完整设计见 `t08_minimal_plan.md`。摘要：

**Step 0（先做，一个脚本、不写新原语、一次 Gazebo 运行）—— 接触可达性探测**

- 用与批次**完全相同**的 profile：`sim_profile.profile(out, "velocity_servo", False, "legacy", 0.0, None)`
  （`run_batch.sh:83`）。
- 起栈后 planning scene 里**没有**任何盒子：只有技能会调用 `add_box`
  （`common.py:544-557`；调用点 `pick_server.py:196,471`、`place_server.py:412,453`），
  所以**不需要做场景手术**，规划器会直接朝接触位姿走——这正是探测想要的条件。
  ⚠️ 但如果这一轮之前已经跑过 PICK，场景里会**同步全部**已知盒子
  （`pick_server.py:438` 调 `_sync_scene_objects`），那时必须先 `remove()` 目标盒子
  （`common.py:589-604`），否则规划器会绕开它、**永远不会接触**。
- 依次把 EE 移到 z = 0.1775、y = 0 的 x = 0.265 / 0.250 / 0.240（相对 box_a 中心 0.220），
  每次前后各采一次 `capture_ground_truth.py`（`benchmark/evaluators/capture_ground_truth.py:26-37`，
  走 gz Pose_V，与技能服务器同一个 helper）。
- **判据（全部为「物体位移」，不是「机器人动了」）**：
  1. 至少 2 个位姿 `move_to_pose` 返回 SUCCEEDED 且 `position_error_m ≤ 0.02`；
  2. box_a 的 gz 位移**单调增加**且 ≥ 30 mm；
  3. 位移方向与 −x 的余弦 ≥ 0.9；
  4. 侧向（|Δy|）≤ 20 mm，|Δz| ≤ 20 mm；
  5. 全程 `carry.engaged == False`。
- **任一条不成立 → T08 = NOT_FEASIBLE，停手**。这就是「先做哪个」的证据化答案：
  否证成本是一次运行，不是一周开发。

**Step 1（Step 0 通过后）** 新增 `PushObject.action` + `push_server.py`：
五个相位仿 `place_server.py`，**复用** `MoveToPoseClient` / `sample_gz_pose` / `GripperClient`，
不新增运动原语、不改世界、不改物理插件。唯一与现有技能**相反**的一条：
**不把目标盒子加进 planning scene**（否则规划器绕开它，见 `pick_server.py:468-472`）。

**Step 2** 走冻结流程新增 `push:<obj>` 子句 + 生成器模板 T08。

### 2.6 判据设计与防假成功

截至今天，验收器**看不见**一次推动（`verify.py` B1/B3/B3b）。所以新增子句时必须
同时封住「假成功」。仓库里已有一条真实教训可引用：
`setup/acceptance/evobot_skill_growth_20261111/README.md:50-58` 记录了
**stage 报执行、物体原地不动**的情况；`docs/HANDOFF.md:342` 记录 `夹爪扫飞方块` 被当成功拦截。
两件事合起来就是「假成功」的两大来源：**没发生却报成功**，和**发生了但不是要的那个动作**。

| 假成功路径 | 封堵信号 | 出处 |
| --- | --- | --- |
| 夹住/吸住带走 | `carry.engaged == False 且 object_id == ''`（composite 已把这条当作硬前提） | `contracts/composite.py:96` |
| 物体被推飞 / 甩出去 | 终态静置高度 `abs(z − 0.0175) ≤ 0.02` | 阈值先例 `evaluate.py:22` |
| 推歪成侧向偏移 | 侧向分量 ≤ 0.02 m、方向余弦 ≥ 0.9 | 新子句参数（Step 2） |
| 一把推到桌子另一头也算过 | 位移**上界** 0.15 m（超过 4 个盒宽） | 新子句参数 |
| 机器人动了物体没动 | 位移由 **gz 真值**测，不由技能 outcome 测 | `capture_ground_truth.py:26-37`；`observe_from_run.py:1-18,85-94` |
| 接近时先把它撞跑了，然后「推」了个已经到位的东西 | 接触前一次采样必须与声明初值一致（≤ 0.015 m），否则整任务 INVALID | `evaluate.py:23` 的 0.015 |
| 位移是两次动作累加 | 只从**任务声明的初值**量，不从「上一次调用前」量 | 生成器 spec 的 `initial_pose`（`generate.py:69-70`） |
| 用了过期观测 | 采样 `max_age_s=0.5` | `place_server.py:361,442` 的用法 |

**位移下限 X = 30 mm 的三个锚点**（不是拍脑袋）：
1. `pick_server` 自己的「物体真的跟着动了」阈值 `box_follow_min_m = 0.03`
   （`config/week1.yaml:40`）；
2. 验收器「没动」的带宽 0.015（`evaluate.py:23`），30 mm = 它的 2 倍，不会与噪声混淆；
3. 盒子边长 35 mm，30 mm ≈ 0.86 个盒宽——**一看就不是抖动**。

新增子句必须**只增不减**（这是仓库既定原则，有先例：`evaluate.py:111-119,132-142`
两处注释都写明「new clause / only ADD」），并登记到 `docs/FREEZE_CHANGELOG.md`
（该文件存在，流程见其 :1-42 以及 `docs/AGENT_HANDOFF.md:295,367`）。

---

## 3. T07 / T09 / T10（各一行 + 一条更正）

**T07 堆叠 — FEASIBLE_WITH_PRIMITIVE_WORK，但阻塞点被现有文档写错了。**
`TASK_CATALOG.md:39` 与 `generate.py:54` 都说「no primitive places at a stacked height;
release clearance is set for table height」。**这两句与代码不符**：
`place_server.py:278` 直接取 goal 里的 z（`place_pos = [pp.x, pp.y, pp.z]`），
`:286` 的释放高度是 `place_pos[2] + clearance`，`:449,473` 用**三维**距离
`dist3(box_after, place_pos)` 判落点——**没有一处假设桌面高度**。
真正的硬阻塞在别处，而且是算术性的：`composite.py:45` 规定 `clearance_m ∈ [0.05, 0.25]`，
而堆叠节距 = 盒高 = 0.035 m，于是 `prepare_plan` 在 `composite.py:81-82` 用
`vacant()`（`:116-117`）判「目标点被占」，**必然拒绝**——`verify.py` C2/C3 用真实代码复现，
对照组 C1（同高度普通放置）通过。评分侧反而**早就有**：`evaluate.py:121-130` 的
`min_tiers` 子句 + `:24` `STACK_TIER_HEIGHT_M=0.030`，而 `generate.py:87,92-93`
的 `min_tiers` 管道**至今没有任何模板用过**。→ 要做 T07，先决定「松开 composite 的
clearance 下限」还是「让堆叠走另一条动作通路」；这是**契约决策**，不是原语开发。
（另注：box 中心 0.0175，叠第二层 0.0525；EE 需到 0.2245，包络 0.3004 ≤ 0.35 ✅，
见 F3——臂展不是限制。）

**T09 杂乱 — NOT_FEASIBLE（作为一个独立能力）。**
世界是 `sim_profile.py:25` 的三选一白名单，物体位姿是硬编码常量
（`generate.py:39-51`、`sim_profile.py:157-167` 只是把一个现成 .sdf 追加进去），
**仓库里没有任何「避开碰撞地摆放干扰物」的代码**——所以 `generate.py:56` 的理由是准确的。
但更根本的问题在 mission 侧：观测是 **oracle 真值**
（`composite.py:93` 强制 `source == 'SIMULATION_GROUND_TRUTH'`；`config/week1.yaml:22`；
`capture_ground_truth.py:26-37`），所以「在多个干扰物中**识别**并操作指定目标」
里「识别」这一步**不会发生**，任务退化成「物体从 3 个变 4 个」——
`docs/EVOBOT_NORTH_STAR_MISSION.md:134` 明确禁止这种包装。
*最小可验证替代方案*：把 T09 改成**感知任务**，走已有的 AprilTag 路径
（`sim_profile.py:242-246`、`docs/Q8_PILOT_20261005.md`），并让批次打开相机
（当前批次 `camera=False`，`run_batch.sh:83`）。那是一条独立的感知研究轴，不是「加几个盒子」。

**T10 受约束放置 — NOT_FEASIBLE（在现验收器契约下）。**
执行侧**已经跑通并且有实测**：`sim_profile.py:168-187` 的 `constrained_approach` 场景
（顶上 0.12×0.12×0.01 静态板），`setup/acceptance/c13_constrained_20261110/README.md:14`
中 legacy **PASS 6/6，29.6 s**。缺的是两件：任务级约束**无法声明**
（`msg/TaskConstraints.msg:1-8` 只有动作菜单/预算/容差/profile/时效，没有几何约束），
以及**不可评分**：验收器是终态纯函数（`evaluate.py:5-8,42`），而「受约束放置成功」的终态
与「自由放置成功」的终态**完全一样**，差异在路径上，验收器看不见路径。
*最小可验证替代方案*：不要把它做成第 10 个模板，把它做成 T01–T06 的**难度轴**
（`sim_profile.profile(..., scene='constrained_approach')` 已经支持），
并在报告里如实写成「同一终态、更深路径」——**不新增任务数**，
正好符合「不能为了凑数引入任务」。

---

## 4. UNKNOWN（写明验证方式，不填猜测）

| # | 未知 | 为什么现在不能答 | 怎么一次答掉 |
| --- | --- | --- | --- |
| U1 | 夹爪/手的**碰撞几何**在 Gazebo 里长什么样、相对 `end_effector_link` 的偏移是多少 | `end_effector_link` 在 URDF 里，而 URDF 来自**未 vendored** 的上游包 `open_manipulator_description`（`launch/trusted_sim.launch.py:32-34`）；本仓库没有 URDF 副本 | 起栈后 `gz model -m open_manipulator_x -i` / `ros2 run tf2_ros tf2_echo world end_effector_link`，把接触面高度定死 |
| U2 | 接触面是否真的落在**盒子高度**（z ≈ 0.0175–0.035） | 同上，属 U1 的直接后果 | Step 0 探测第 1 步的判据就是它（位移随 x 单调增加才说明接触发生在盒侧） |
| U3 | 沿轨迹推时 ros2_control 位置控制器会不会**因跟踪误差中止** | 本栈从未命令过「进入障碍」的轨迹；等价失败形态没有归档 | Step 0：若 `move_to_pose` 返回 `ERR_POSE_NOT_REACHED`/`ERR_EXECUTION_FAILED` 而物体没动 → 位置控制不接受阻塞 |
| U4 | 叠第二层后上层盒会不会**弹飞/滑落**（首步穿透的经典问题） | 本栈无任何叠放运行；相邻工作流的「t0 生成在桌面以下被弹起 106 mm」是 MuJoCo/LIBERO，**不可迁移** | T07 决策后做一次 release-only 实验即可 |
| U5 | 4-DOF 无腕滚时，横向平移会不会让末端姿态漂移、接触点高度改变 | `move_to_pose` 默认不强制姿态（`move_to_pose_server.py:111`），只能实测 | Step 0 同时记 `reached_pose.orientation` 与 Δz |
| U6 | 推的成功率 / 重复性 | 本卡没有跑过任何一次推动 | Step 1 之后才谈 n≥N |

---

## 5. 我不宣称什么

- **不宣称任何 rung**。按 `docs/EVOBOT_VISION.md:55-66` 的六级证据阶梯，本卡连
  `Designed` 都只对 T08 的 Step 0 部分成立；本文是**评估文档**，不是能力记录。
- 不宣称 T08 **已经**可行——只宣称「没有原语级阻塞，且否证成本很低」。
- 不宣称「接触位移 = 推动能力」。前者是**意外**记录（HANDOFF:342、pick_server:469），后者**没测过**。
- 不宣称 T09/T10 **永远不可行**；只宣称**在现契约下不可评分**，并给出重铸方案。
- 不宣称 `TASK_CATALOG.md`/`generate.py` 的理由是错的——只说 T07 那一条的**归因**与代码不符（§3）。
- 不声明任何成功率、方差、MTBF。

---

## 6. 文件与复现

| 文件 | 内容 |
| --- | --- |
| `README.md` | 本报告 |
| `claims.tsv` | 每条结论 → 证据 file:line → 由哪个检查项复核 |
| `verify.py` | 只读论证检查器（26 条断言，不跑仿真） |
| `verify_result.json` | 上述检查的机器可读结果（由 verify.py 写出） |
| `t08_minimal_plan.md` | T08 的最小可验证实现方案（Step 0/1/2 + 判据 + 防假成功） |

```
python3 setup/acceptance/evobot_p2_feasibility_20261111/verify.py
```

**没有跑的东西（如实列出）**：没有起 Gazebo，没有起 MoveIt，没有调用任何技能，
没有做 Step 0 探测，没有测 IK 可达性（U1/U2/U3 全部依赖实机/仿真）。

Repo: `/mnt/c/dev/flexcell`（= `C:/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp`）。

**git 归属说明（必须写清楚）**：本卡**没有执行任何 commit 或 push**。开工时 HEAD = `4a97c250`。
写作期间并发会话提交了 `b396e340`（`2026-11-11 18:38:51 +0800`，
"experiment(baseline-a): A-v1 tolerance contrast, designed but not yet run"），
该提交用 `git add -A` **把本目录当时的 5 个文件一并带进了版本库**——不是本卡做的。
本卡其后对 `t08_minimal_plan.md` 的那次修改因此显示为 `M`。
也就是说：本目录的**内容**是本卡的，**提交动作**是别人的；如需把这批文件从那条
Baseline-A 提交里拆出来，那是 lead/该提交所有者的决定，本卡不擅自 revert。
