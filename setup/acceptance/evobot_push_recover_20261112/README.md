# push_recover：首次真实运行与 ACCEPT/REJECT 决策

**日期** 2026-11-12 · **策略首版** commit abf865b7 · **Gazebo** 5 次真实推

**决策：REJECT 首版策略；signed-displacement 修复 ACCEPT（待复测）。任务级结果 UNKNOWN。**

---

## 一、运行结果（接触高度 0.0200，最多 3 次尝试，起点 x=0.22）

| 试次 | 尝试 | 策略记录推进 | 物体终点 x | 实际方向 | 终态判定 |
| --- | --- | --- | --- | --- | --- |
| 1 | 3 | 65.87 mm | 0.2935 | +x 反向 | False |
| 2 | 3 | 28.09 mm | 0.3597 | +x 反向 | False |
| 3 | 1 | 144.63 mm | 0.0753 | -x 正确 | False |
| 4 | 1 | 92.20 mm | 0.1142 | -x 正确 | False |
| 5 | 3 | 72.45 mm | 0.4069 | +x 反向 | False |

---

## 二、抓到两个 bug：一个在我的策略里，一个在我的测量里

### Bug 1（策略）—— 用了无符号幅值

```python
moved = result.get("displacement_m")        # 错：这是位移的模
```

物体被弹向反方向时，模仍是正数，被计成「有进展」。
于是策略在试次 1/2/5 一路「恢复」，把方块从 0.22 推到 0.29 / 0.36 / 0.41。

正确字段是 `displacement_along_direction_m`（带符号投影）。已修，加 3 个测试；
把实现改回读模，3 个具名测试立刻变红。

### Bug 2（测量）—— 用 `passed` 而非 `terminal_passed`，且未提供轨迹

试次 3 的实际指标全部合格：

```
displacement_m    = 0.14471    在 [0.030, 0.150] 内   OK
vertical_m        = 0.0                              OK
direction_cosine  = 0.99976                          OK
inside_zone       = True                             OK
```

却判 False，原因是：

```
reason = no trajectory for this object: end state alone cannot
         prove it was pushed rather than carried
trajectory_required = True
```

这是 v0.4.0 的 fail-closed 设计在正常工作——只喂终态、不喂轨迹，
它拒绝认证一个「看起来对但缺过程证据」的运行。**不是机器人失败，是我的测量缺陷。**

---

## 三、这次运行真正建立的新事实

### 物体经常被推向反方向（3/5）

```
试次 1: +73.5 mm
试次 2: +139.7 mm
试次 5: +186.9 mm
```

此前只知道「有时推不动」，现在知道「有时被推向反方向，而且推得很远」。
与 135 mm 方差的机制一致：不是接触维持不住那么简单，而是末端在接触瞬间从方块上棱滑过，
把它向后甩出。

**这仍是现象描述，不是根因。根因状态 UNKNOWN 不变。**

### fail-closed 验证器确实会拒绝

一次「终态完全合格」的运行因缺轨迹被判 False。
**这是 verifier 有效性的真实正面证据，不是负面证据。**

---

## 四、决策

| 项 | 决策 | 理由 |
| --- | --- | --- |
| push_recover 首版策略 | REJECT | 用无符号幅值，把反向运动当进展 |
| signed-displacement 修复 | ACCEPT（待复测） | 逻辑已修、测试与变异已证；尚无物理验证 |
| T08 任务通过率 | UNKNOWN | 本批缺轨迹证据，passed 恒为 False，不可统计 |
| push_recover 作为新技能 | 未达任何有效级别 | 仅 Designed/Implemented/Unit Tested，未到 Simulation Tested |

---

## 五、下一步（已明确，本轮未做）

1. 驱动里接 `evobot_z_tracker.py` 记录 `max_z_m`，把轨迹喂给评估器；
2. 用修复后的策略重跑 5 次；
3. 只有「终态 + 证据」双通过，才谈 Simulation Tested；
4. 若反向甩出占多数，说明该改的是接触点几何而非重试策略，届时按 §3 记录可行性并转向。

---

## 六、成本

| 项 | 值 |
| --- | --- |
| LLM 调用 | 0（全部本地策略与仿真） |
| Gazebo 运行 | 5 次，约 12 分钟 |
| PushObject | 未改（git diff 为空） |
| 阈值 / 评估器 | 未改 |
