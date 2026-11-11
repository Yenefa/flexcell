# MISSION UPDATE — goal round 3 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Start HEAD** 0a64dfd1 · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮问题

上一轮收尾时我写：「执行器的判决和世界的状态是不同的测量，在这批上两者约 30% 不一致」。
本轮的问题是：**这个不一致到底是什么？**

答案是**一个缺陷**，而且它在整个项目历史里都有。

## §19.2 根因：`place` 用夹爪孔径判断物体是否被释放

所有 A′ 失败都是同一条链：

```
composite ec=62「native terminal/verification unconfirmed」
  ← pick_place_v1 outcome=1 ec=50（ERR_SKILL_FAILED）
    ← place ec=25「gripper did not open (position=-0.011 requested=0.02 stalled=True)」
    ← episode「policy abort (NON_RECOVERABLE): place failed ...  trace=PICK_A(attempt=1):OK,PLACE_A:FAIL」
```

**`PICK_A:OK` 每一次都成功。** 失败永远在 `PLACE_A`，永远是同一个原因。

触发点 `place_server.py:424-432`：`aperture_error > 0.005` 且 `not reached_goal` 时失败，
`gripper_open_position = 0.02`。

但 G1 标定实测**自由空间**开爪只到 **0.0104**——所以即使两指之间什么都没有，
`aperture_error = 0.0096 m`，**接近 0.005 m 容差的两倍**。这个检查能通过，纯粹靠 `reached_goal` 兜住；
**它离「拒绝每一次放置」只差一个标志位。**

## §19.3 为什么夹爪与物体无关

`carry.jsonl`：搬运是 **`velocity_servo` pin**，offset 的 z 分量 = **−163.8 mm**。
**箱子被钉在离工具坐标系六分之一米处，手指从未接触它。**

这个数与 T04 的 `pick.attach_gap_m = 0.1646 m` 是同一个量，从完全不同的方向独立得到。

**所以孔径不可能是关于物体的证据。** 而真正的释放确实发生了：
`place` 返回 `released: false`，同一 run 的 `carry.jsonl` 记录 `{'event':'stop','cause':'release','engaged':true}`。
pin 在 abort 时释放，把箱子丢在它被搬到的地方——正是目标点。**这就是为什么 7 次「失败」里 4 次仍然评估通过。**

## §19.4 频率与历史范围

| 口径 | 数值 |
| --- | --- |
| place 尝试 | **12 / 63（19%）** — A′ 7/29，B 5/34 |
| run 级 | **12 / 32（37.5%）** — A′ 7/16，B 5/16 |
| 全项目历史 | **51 / 539（9.5%）**，21 个 acceptance 归档，最早到 20261010 |

最严重的是**项目一直在引用的那几批**：
P0 A′ 24.1%、goal-check A/B 16.7%、pooled n=32 16.7%、crosstype 14.7%、unseen n6 14.3%。

## §19.5 它推翻了什么：B 的「架构优势」不成立

上一轮我写：差异是**架构性**的——B 有恢复层，救回 2 个失败（14/16 → 16/16），A′ 是一次性所以停在 13/16。

**查了那两次，而不是假设。两次的首轮失败都是同一个缺陷：**

```
HO-2efba46248da  failed_stage=target_box_a-0  completed_stage_ids=[]
HO-d3ab212142de  failed_stage=target_box_b-0  completed_stage_ids=[]
两者 native_error_code=50  trace=['PICK_A(attempt=1):OK','PLACE_A:FAIL']
     native_detail='place failed (ERR_PLACE_FAILED ... legacy_error_code=25)'
```

**所以 B 的全部「恢复优势」= 重试它自己的 place 缺陷，第二次夹爪恰好开了。**
它救的是两个**缺陷导致的失败**，不是两个**困难任务**。

| | 本轮之前 | 本轮之后 |
| --- | --- | --- |
| B 相对 A′ 的优势 | 「架构性：恢复层」 | **「围绕自身缺陷的重试循环」** |
| 谁更强 | 「大致相当，B 有恢复」 | **两侧都无法区分；唯一测到的差异是伪影** |

**我不声称 A′ 会赢。** 我声称这个比较**无法区分两者**，因为唯一测到的差异是一个两侧都会踩的缺陷的重试。

## §19.6 对目标记账的意义

Master Goal 要求 False Success 为 0，并且**必须报告 False Failure**。这是一个 False Failure 机制，
它在整个项目历史中一直抬高所有基于执行判决的失败率。

诚实的表述不是「数字错了」，而是：**执行器的判决测量的是执行器的自我报告，不是世界**；
而这个项目反复把它当作后者。任务级评估读世界，执行判决读技能对自己的看法。**两者在 37.5% 的 run 上不一致。**

## §19.7 能力等级（不膨胀）

| 项 | 等级 |
| --- | --- |
| place 释放判据缺陷 | **根因确认，机制/频率/历史范围均已测量** |
| 修复 | **未实施** — `place_server.py` 是冻结契约，需人工批准 |
| P0 A′ vs B 排序 | **无法区分**——唯一差异是伪影 |
| T08 | 未变，skill 级 0/6 |
| L4 Develop | **未跨过** |

## §19.8 修复（一行，待批准）

把 `released` 改为来自 **carry 后端**的释放确认（`carry.jsonl` 已记录），夹爪检查降级为**诊断项**，
不得覆盖已释放的 carry。**未实施。**

## §19.9 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0**（本轮全部为离线日志分析） |
| 孤儿进程 | 0 |
| 冻结文件改动 | **0** |
| 阈值改动 | **0** |
| 删除失败证据 | **0** |
