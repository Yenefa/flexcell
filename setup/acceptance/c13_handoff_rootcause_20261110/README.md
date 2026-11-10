# C13b — MTC 轨迹交接失败：**根因未确定（UNKNOWN）**

> 本文件在写的过程中被我自己的数据推翻过一次。两个错误版本都保留在 §5。

## 1. 现象

C13 公平场景下 MTC 在 `PLACE_B` 失败：
```
ValueError: measured start state differs from planned trajectory
(move_to_pose_server.py:288, _consume_mtc)
```
`elapsed_ms = 2`，在 `PLANNING` 阶段立即失败——不是超时，也不是规划失败。

## 2. 代码事实（已核实完整表达式，未被截断）

```python
if joints is None or age is None or age > .5 or any(
        name not in positions
        or abs(positions[name] - trajectory.joint_trajectory.points[0].positions[i]) > .03
        for i, name in enumerate(trajectory.joint_trajectory.joint_names)):
    raise ValueError('measured start state differs from planned trajectory')
```

- **容差是 0.03 rad**，存在，不是"精确相等"；
- 遍历的是 **`trajectory.joint_trajectory.joint_names`**；
- 实测该字段为 `["joint1","joint2","joint3","joint4"]` —— **只有 4 个手臂关节**；
- 因此**夹爪不参与比较**。

## 3. 那么触发的是谁

失败时刻实测手臂关节：

| joint | 实测值 |
| --- | --- |
| `joint1` | 0.20741 |
| `joint2` | -0.19189 |
| `joint3` | 0.36006 |
| `joint4` | -0.44359 |

**但被比较的对象是"交接轨迹的起点"，而这个值没有写进日志。**
所以从归档数据**算不出**确切差值。

## 4. 结论：**UNKNOWN**

我只能确定：
1. 失败发生在 `_consume_mtc` 的起始状态比对；
2. 容差是 0.03 rad；
3. 参与比较的只有 4 个手臂关节；
4. **无法从归档证据确定是哪个关节、差多少、以及为什么轨迹起点与实测不符。**

要定论，必须**在 `_consume_mtc` 里把 `trajectory.points[0].positions` 一并写进日志**，
然后重跑。在那之前任何"根因"叙述都是猜测。

## 5. 我在这个文件里犯的两个错误（都保留）

### 错误 1：「没有容差」
我最初写"`abs(delta)` 没有和任何容差比较，要求精确浮点相等"。
**错。** 真实代码是 `> .03`。我漏看是因为读取时把该行**截断显示**了。

### 错误 2：「夹爪关节差 0.031 触发」
我随后算出 `gripper_left_joint` 从 -0.011 变到 0.020，差 0.031 > 0.03，
于是断言"夹爪张开触发了检查"。**也错。**

原因：我比较的是**相邻两次运行之间**的实测值，
而代码比较的是**实测值 vs 交接轨迹起点**。两者不是一回事。
而且夹爪根本不在 `joint_names` 里。

## 6. 这两个错误的共同点

**我连续两次用"看起来自洽"的解释替代了"去取真正被比较的那个数"。**
第一次是没看全表达式，第二次是比错了对象。

规则：**当一个检查失败时，先确认它到底在比较哪两个量，再解释差值。**
