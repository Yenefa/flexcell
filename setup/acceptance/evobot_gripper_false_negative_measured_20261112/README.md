# 夹爪释放误报：任务层实测影响（不修改运行时契约，仅记录证据）

**日期** 2026-11-12 · **来源** Baseline B 真实执行 `T04-train-seed1000`
**性质** 已知问题的新实例，**首次量化到任务层**

---

## 一、发生了什么（完整证据链）

```
seq=1  OBSERVE   outcome=0
seq=2  PICK      outcome=0   picked target_box_b: attached, measured rise 0.098m
seq=3  PLACE     outcome=1   error_code=25 (ERR_PLACE_FAILED)
                 detail = gripper did not open
                          (position=-0.011 requested=0.02 stalled=True)
seq=4  ABORT     policy: NON_RECOVERABLE, carried box is not retried
```

复合执行器：

```
outcome           = 1 (FAILED)
error_code        = 62
detail            = native terminal/verification unconfirmed for target_box_b-0
completed_stage_ids = []          <- 一步都没被确认为完成
component_run_ids = ['pick_place_v1-3a5018f5']
```

**但独立验收：**

```
gt_after  -> evaluate.py v0.5.0 -> passed = True, failed_clauses = []
```

---

## 二、这确认了哪个已知问题

项目早已记录：

```
carry_release_confirmed = True
released                = False
gripper_open.reached_goal = False
GRASP_STALLED
```

本次实例的 `detail` 是同一句的自然语言形式：

> `gripper did not open (position=-0.011 requested=0.02 stalled=True)`

**所以：技能断言「没张开」，但物体确实留在了目标位置。**

### 机制（本次可见的部分）

- 命令夹爪张开到 0.02 rad
- 实测停在 −0.011 rad（仍闭合）
- 技能判定 `stalled=True` → 释放未确认 → PLACE 失败
- **但物体在末端回撤时留在了目标位**

**「夹爪没张开」与「物体没放下」不是同一件事。** 技能把前者当成了后者。

---

## 三、为什么这个证据重要

### 1. 它把「误报」从现象变成了有任务层后果的缺陷

在此之前这是技能层的自述。现在可以量化：

| 层 | 判定 |
| --- | --- |
| 技能 PLACE | ❌ 失败 |
| 复合执行器 | ❌ 失败 (62) |
| **独立验收** | ✅ **通过** |

**同一次运行，上层说失败，独立判据说成功。**

### 2. 它制造的是 False Failure，不是 False Success

mission §9 E 要求两个方向都报告：

```
False Success（自称成功但没通过）: 0
False Failure（实际通过但自称失败）: >= 1  <- 本实例
```

**如果拿复合执行器的 outcome 当成功率，这次会被记成失败，而任务其实完成了。**
这正是 §9 E 警告的「把无法测量写成零 / 用错测量口径」的一种。

### 3. 它说明「用 harness 自述当验收」是错的

本项目已经确立「独立验收器说了算」。这个实例证明那条原则不只是形式——
**harness 自述会反向出错**，不只是会夸大成功。

---

## 四、本轮做了什么、没做什么

| 项 | 状态 |
| --- | --- |
| 定位到具体实例与具体 detail | ✅ 已完成 |
| 建立技能层→执行器层→验收层三级对照 | ✅ 已完成 |
| 判断「物体为什么到位」 | ❌ **UNKNOWN** |
| 修改夹爪释放判据 | ❌ **未做，未经批准不得做** |
| 修改 `place_server.py` 或运行时安全契约 | ❌ 未做 |

### 为什么「物体为什么到位」是 UNKNOWN

可能是：

1. 夹爪实际有微小张开，足以让方块留在原地，但编码器/关节状态读数没反映
2. 方块是靠摩擦/位姿卡在目标处，回撤时被留下
3. 方块从未真正被夹住（PICK 的 attached 判定也是误报）

**这三条都未被区分测量。** 需要释放期间的关节位姿与方块位姿逐帧数据，
本轮没有采集。**不得从中挑一条写成结论。**

---

## 五、对已批准待处理提案的意义

项目记录：「部分释放失败属于技能层误报，相关修改尚待人工批准」。

本文件为该提案提供：

- **一个可复现的具体实例**（`T04-train-seed1000`，证据目录见下）
- **明确的错误码与 detail 字符串**（25 / 62，`gripper did not open`）
- **任务层后果的量化**（一次本应通过的运行被判失败）

**但不构成批准，也不替代批准。** 是否改运行时安全契约仍由人类决定。

---

## 六、证据位置

```
ci-public-window/evidence/b_realexec_diff5_20261112/T04-train-seed1000/
  composite.json          执行器结果 (outcome=1, error_code=62)
  verdict.json            独立验收 (passed=True)
  gt_after.json           真实终态
  sim/episodes/pick_place_v1_pick_place_v1-3a5018f5.json
                          技能层逐步记录 (seq=3 PLACE error_code=25)
  stack.log
```

---

## 七、边界

- **n=1**。一次运行，不是发生率。
- 只在 `T04-train-seed1000` 上观察到；其余 8 次 B 执行 `outcome=0`。
- 因此**不能**说「夹爪误报很频繁」或「影响很小」——**发生率未测**。
- 不影响 False Success = 0 的结论（方向相反）。
