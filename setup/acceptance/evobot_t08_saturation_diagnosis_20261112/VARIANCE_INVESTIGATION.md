# 方差来源调查：相同输入产生 135mm 极差

**日期** 2026-11-12 · **目的** 区分「仿真非确定性」与「接触策略」两种假说

---

## 已测量到的事实（CONFIRMED）

### 1. 五次运行的物理输入逐字节相同

```
world.sdf   sha256 = f78a469d4bb7...   ← 5 次全部相同，distinct=1
params.yaml 逐行 diff：只有 log_dir 输出路径不同，物理参数无差异
```

同一个 goal（distance 0.09、height 0.0200、direction −x）。

### 2. 五次都是真实运动派发，不是基础设施失败

| 试次 | ee_travel | reach_error | 增量 |
| --- | --- | --- | --- |
| 1 | 0.104 | 0.0072 | 3 |
| 2 | 0.160 | 0.0101 | 5 |
| 3 | 0.104 | 0.0061 | 3 |
| 4 | 0.132 | 0.0030 | 4 |
| 5 | 0.160 | 0.0093 | 5 |

**不是 DDS 耗尽、不是 action server 缺失、不是超时**——每次末端确实走了 104–160mm。
所以不能按 mission §9 A 把它记成 HARNESS_ERROR。

### 3. 仿真按墙钟运行

```xml
<physics name="1ms" type="ignored">
  <max_step_size>0.005</max_step_size>
  <real_time_factor>1</real_time_factor>
  <real_time_update_rate>500</real_time_update_rate>
</physics>
```

### 4. 控制目标不是实际接触体

```
配置   week1.yaml / move_to_pose.yaml : end_effector_link: end_effector_link
日志   MoveIt: 'Link end_effector_link has visual geometry but no collision
       geometry. Collision geometry will be left empty.'
真实接触伙伴（contact_steps.jsonl 计数）:
       gripper_left_link   4076 次
       gripper_right_link  4548 次
```

**技能把一个没有碰撞几何的虚拟 link 当作控制目标，而真正在推方块的是两根手指。**

---

## 推断（INFERRED，不是结论）

把上面四条放在一起，一个**能解释**双稳态的机制是：

> 控制目标（虚拟 link）与实际接触体（两根手指）之间存在姿态依赖的偏移。
> `real_time_factor=1` 让物理步进与 ROS 指令到达时刻耦合，
> 于是每次接触瞬间手指姿态有微小差别，可能左指先碰、右指先碰，或只擦到棱。
> 这会把连续的控制量放大成「咬住 / 滑脱」两种离散结果。

**这个推断没有被直接测量证实。** 我没有记录每次接触瞬间的手指姿态，
也没有做 `real_time_factor=0` 的确定性对照。

### 能证伪它的最小实验

1. 在生成的 world 副本上把 `real_time_factor` 设为 0（固定步进），重跑 5 次。
   若方差消失 → 归因于实时调度；若方差仍在 → 归因于控制/几何。
2. 记录每次接触首帧的两根手指位姿，看左右先碰是否与结果分叉对应。

**这两条都没做，所以根因状态 = UNKNOWN。**

---

## 这对已有结论的影响

| 之前的说法 | 修正后 |
| --- | --- |
| 「双稳态接触」 | 保留为**现象描述**；机制 UNKNOWN |
| 「根因是接触高度」 | **部分成立**：0.030 → 0.59mm、0.0200 → 中位 32mm，这个效应是实测的；但它不能解释同高度下的 135mm 方差 |
| 「40% 通过率是技能能力」 | **不能这么归因**。在仿真非确定性未排除前，40% 是「整个栈」的通过率，不是技能的 |
| 「根因是 Control」 | 我第一份诊断这么写过，已被扫描数据推翻；现在也不能据此重新归到 Control |

### 十类归因更新

| 类别 | 状态 |
| --- | --- |
| Control（接触高度选择） | ✅ 实测效应，但只解释均值不解释方差 |
| Control（丢失后不重试） | ✅ 代码事实，真实但次要 |
| **Tooling（控制目标无碰撞几何）** | ✅ **实测到，可能是方差主因，未证实** |
| **Runtime（real_time_factor=1）** | ✅ **实测到，可能是方差主因，未证实** |
| Environment（仿真确定性） | ⚠️ UNKNOWN，需要对照实验 |
| Perception / Planning / Kinematics / Grasp / State Management / Model Reasoning | ❌ 各有证据排除 |

---

## 为什么停下

继续在 dev 实例上调接触高度只会拟合噪声。
mission §9 C 禁止把已用于开发的实例当成 held-out；§9 F 要求声称根因前有能区分假说的测量。

**下一步应当是上面的实验 1（固定步进对照），而不是再调一次参数。**
它不改动任何阈值、不改动技能实现、不触碰 held-out，且能明确区分两种假说。
