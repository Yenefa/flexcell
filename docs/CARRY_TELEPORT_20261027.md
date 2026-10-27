# teleport carry 的实测行为（2026-10-27）

一次本地、无头、可复现的运行，第一次把抓取过程中箱子的连续轨迹录了下来。

## 结论

**箱子不是"没跟上"，是"每 0.1 秒被瞬移一次，其余时间在掉落"。**测量的 `rise` 是这条锯齿曲线上采样点的值，不是抓持质量的度量。

| 观测 | 值 |
| --- | --- |
| 夹爪（左指）z，抬升段 | 恒定 0.2610 m |
| 箱子 z 振荡范围 | 0.0090 → 约 0.12 m（单轮 0.1254 / 四轮 0.1226） |
| 振荡周期 | **0.101 s**（= pin 周期 0.10 s） |
| 单周期回落 | **0.066 – 0.070 m**（随测量窗口，取 0.067） |
| 相对 pin 目标（gripper − 0.16）的偏差 | 全程 **−0.092 … +0.018 m**，峰峰约 70 mm |
| 四轮全程，箱子相对 pin 目标落后 > 50 mm 的帧 | **约 6 成**（口径见下） |

## 两次运行

**运行 A（单轮，录 44 s）**：`pick_ok=true`，rise **+0.0764 m**；同配置再跑一次 rise **+0.0623 m**。两次都"成功"，差 14 mm。

**运行 B（四轮，录 147 s）**：

| trial | pick_ok | error | rise |
| --- | --- | --- | --- |
| 1 | true | 0 | +0.0737 m |
| 2 | **false** | **23** | **−0.0083 m** |
| 3 | true | 0 | +0.0629 m |
| 4 | true | 0 | +0.0811 m |

**第 2 轮在本地复现了历史种群的形状**：code 23 + 负 rise（历史 92 条的中位数是 −0.0003 m）。

而 `−0.0083 = 0.0092 − 0.0175`：箱子起始中心高 0.0175 m（35 mm 立方体的半高），测到的 0.0092 m 正是这条锯齿的**最低点**。也就是说，这一轮被判失败，是因为最终测量恰好落在振荡的谷底——同一条曲线上任何高点都会给出 +0.08 左右的"成功"。

## 这意味着什么

1. **`box_follow_min_m = 30 mm` 测的是采样相位。**它把"采样站在哪"当成了"有没有抓住"。
2. **历史成功率被这个伪影污染。**所谓 9/10 成功，是采样点碰巧落在高位。
3. **DetachableJoint 从"改善"变成"必需"。**探针已证明它在静态父体下 6/6 可用、刚性误差 0.0000 m（见 `docs/BACKEND_ADMISSION_20261027.md`）。这一条与本文档正好互为因果：问题确认了，解法也验过了。
4. **不要去调 30 mm 这个阈值。**给一个假指标调参，只会让数据看起来更好、结论更错。

## 运行 C：完整 demo（端到端）

`ros2 action send_goal /run_demo` 一次跑完 OBSERVE→PICK→PLACE→VERIFY ×2：

```
outcome: 0 (SUCCEEDED)   duration 27.79 s
PICK_A(1):OK  PLACE_A:OK  VERIFY_A(1):OK
PICK_B(1):OK  PLACE_B:OK  VERIFY_B(1):OK
object_a_at_zone: true   zone_a_error 0.0094 m
object_b_at_zone: true   zone_b_error 0.0050 m
evidence_id: local-live-20261027-b95ba331
```

**这件事要反过来读**：端到端 demo 是成功的，但抓持语义仍然是假的。teleport 确实把箱子"拖"到了目标区（区域误差都在 5 cm 容差内），所以演示看起来很漂亮——问题只暴露在 PICK 那一瞬间的测量上，而那里 5 次里失败了 1 次。

**这正是不能只看端到端演示的原因**：一次漂亮的 demo 不能证明附着语义可信。要让"成功"这两个字有意义，必须先让箱子真的跟着走。

## 它是 #32/#13 的根因吗

**这是一个与数据一致的机制解释，不是已证明的根因。**要说"就是它"，还差一步：换到 DetachableJoint 之后，在同一 world、同一 PICK 契约下重新测量——若绑定后箱子稳定跟随、rise 稳定为正且方差大幅收敛，则证实；若仍然锯齿，则还有第二层原因。

这个验证很便宜（一次 A4 窗口 + 同一套 50 Hz 采样），应当作为后端接入后的第一件事。

## 一处已撤回的说法

初稿写过"四轮全程，箱子靠近夹爪的帧为 0 / 7372"。**这句话撤回。**

它用的是 `box − gripper > −100 mm` 这个门槛，但 `carry_offset = 0.16 m`：箱子中心在夹爪下方 16 cm 是**设计值**，所以"完美跟随"对应的就是 −160 mm，−100 mm 物理上不可能达到。换成正确口径（相对 pin 目标 `gripper − 0.16`）后，结论不是 0%，而是箱子**始终在目标附近振荡**——问题不在"从来没靠近"，而在"每 0.1 秒离开再回来"。

这个错误和 #52 里那个"最低 rise 下界"是同一类：**用一个看起来合理的门槛，得出一个物理上不可能满足、因而必然为 0 的结论。**对账时才发现。

## 这次没做的

- 总样本只有 **6 次 PICK**（A1、A1b 各 1 次，A4 四轮）、1 次失败；**不构成失败率估计**，也不据此宣称历史失败全部由相位导致。
- 只看抬升 + 保持段；释放、放置段未做同样采样。
- 只有一个物体（A）、一个 world、一个 backend、一台机器。
- 采样走 Gazebo 位姿话题，未经 ROS；**sim 时间与其他时钟未做对齐**（这正是下一步 P0 规格要补的三列时钟）。
- pin 目标用的是 `gripper_z − 0.16` 这个近似（来源是 `carry_offset`），不是从系统内部读出的 pin 目标值。

## 复现

```bash
source /opt/ros/jazzy/setup.bash
source ~/agentic_workcell_ws/install/setup.bash
export ROS_DOMAIN_ID=45 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

bash setup/flexcell start
(timeout 150 gz topic -e -t /world/empty/dynamic_pose/info \
   -n 9000 --json-output > poses.jsonl &)
python3 setup/111_grasp_probe.py --object target_box_a --trials 4 --out A4.jsonl
bash setup/flexcell stop
```

两个坑：栈在 domain 45 + cyclonedds，不导出会看不到任何节点；WSL 会话结束会回收整个栈，起栈/采样/停栈必须在同一次会话内完成。

## 证据位置

`setup/acceptance/local_run_20261027/`：`A1.jsonl`、`A1b.jsonl`、`A4.jsonl`、`trajectory.csv`、`poses.jsonl.gz`、`poses4.jsonl.gz`、`start*.log`、`health_after.json`、`stop*.log`。
