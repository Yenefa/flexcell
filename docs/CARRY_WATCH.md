# carry watch —— 抓持跟随质量的观测工具

`setup/114_carry_watch.py`。一个离线 / 在线两用的小工具，用来回答一个问题：

> **箱子到底有没有跟着夹爪走？**

配套的实测背景见 [`docs/CARRY_TELEPORT_20261027.md`](CARRY_TELEPORT_20261027.md)：
teleport 后端每 0.1 s 把箱子 pin 一次到夹爪下方，其余时间箱子自由下落，
于是 PICK 的 `rise` 测到的是"锯齿曲线上采样点的值"，而不是抓持质量。
同一个抓持，采样落在波峰给 +0.08，落在波谷给 −0.008 —— 历史"成功率"就是这么来的。

本工具不测 `rise`，它测**这条曲线本身的形状**，把观测判成三种之一：

| 判定 | 含义 | 物理图像 |
| --- | --- | --- |
| `SAWTOOTH` | 周期性锯齿 | 箱子每 0.1 s 被瞬移一次，其余时间在掉落（teleport 伪影） |
| `CONSTANT_OFFSET` | 稳定跟随 | 箱子刚性跟着夹爪，只差一个恒定偏移（**换刚性后端后期望的结果**） |
| `NO_CARRY` | 没跟上 | 箱子没被带起来，或 delta 一直很大又不具周期性 |

只依赖 Python 标准库（gzip / json / argparse / statistics / subprocess）。没有 numpy/pandas。

---

## 用法

### 离线（主要用法）

栈不能常驻，所以先录、后分析：

```bash
python3 setup/114_carry_watch.py --poses setup/acceptance/local_run_20261027/poses4.jsonl.gz
```

支持 `.jsonl` 和 `.jsonl.gz`。加 `--json out.json` 额外写一份机器可读结果
（`-` 表示打到 stdout）。

### 在线

```bash
source /opt/ros/jazzy/setup.bash
source ~/agentic_workcell_ws/install/setup.bash
export ROS_DOMAIN_ID=45 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

python3 setup/114_carry_watch.py --follow -n 9000
```

工具自己起 `gz topic -e -t /world/empty/dynamic_pose/info -n 9000 --json-output`
子进程，实时打印每帧 `t,box_z,grip_z,delta`，结束（或 Ctrl-C）时给判定。
世界名用 `--world` 改（默认 `empty`，**不是** `flexcell_world`）。

### 常用参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--box` | `target_box_a` | 箱子模型名 |
| `--gripper` | `gripper_left_link gripper_right_link` | 夹爪，多个取 z 均值 |
| `--rest` | 自动 | 箱子静止高度（默认取全程 box_z 中位数） |
| `--grip-thr` | `0.15` m | 夹爪 z 抬升阈值 |
| `--lift-margin` | `0.005` m | 箱子高出静止多少算"被带起来了" |
| `--hold-speed` | `0.05` m/s | 保持段夹爪速度上限（见下） |
| `--period` / `--period-tol` | `0.100` / `0.030` s | 期望 pin 周期与容差 |
| `--pp-thr` | `0.030` m | 单周期峰峰阈值 |
| `--offset-tol` | `0.005` m | 稳定跟随的 delta 变化上限 |

### 退出码

- `0` —— 判定成功执行（**不管判定是什么**，SAWTOOTH 也是 0）
- `2` —— 输入不可用（文件不存在 / 一条位姿都没解析出来）或没找到目标模型

所以脚本里判断"后端修好了没有"要读 `verdict` 字段，不能只看退出码。

---

## 判定是怎么做出的（要能解释）

1. **取 delta**：`delta = grip_z − box_z`，每帧一个。夹爪 z 取左右指均值。
   proto3 会省略零值字段（`"position":{}`），缺的键一律按 0 处理。
2. **找抬升段**：`grip_z > --grip-thr` **且** `box_z > rest + --lift-margin` 的连续帧。
   锯齿的波谷会短暂掉到 margin 以下，所以中断不超过 `--gap`（默认 3）帧的合并成一段。
   短于 `--min-frames` 的段丢弃。取**最长的一段**作为主抬升段。
3. **收窄到保持段**：在主抬升段里找最长的"夹爪几乎不动"（`|d grip_z/dt| < --hold-speed`）的
   连续子段，用它做振荡分析。
   *为什么*：抬升段的头尾夹爪本身在走 commanded motion，delta 里混着指令运动，
   会稀释振荡幅度。保持段里夹爪不动，delta 的变化就纯粹是箱子的振荡。
4. **找局部极小**：在 delta 序列上取局部极小。局部极小 = 箱子最靠近夹爪的时刻（锯齿的波峰）。
5. **周期**：相邻局部极小的**时间间隔均值**。
   **单周期峰峰**：每个局部极小到紧随其后的局部极大的摆幅，取均值 ——
   也就是"一个 pin 周期里箱子掉下去多远"（报告里叫"单周期回落"）。
   帧数不足时（局部极小 < 3 个）不谈周期。
6. **判定**：
   - 局部极小 ≥ 3 **且** 周期落在 `0.100 ± 0.030` s **且** 单周期峰峰 > 30 mm → `SAWTOOTH`
   - 否则若 delta 变化 < 5 mm → `CONSTANT_OFFSET`
   - 否则 → `NO_CARRY`

报告里同时给出抬升段时长、帧数、采样率、delta 最小/最大/峰峰、
局部极小个数、平均周期、单周期峰峰，以及一句人话理由。

---

## 阈值为什么定在这

| 阈值 | 值 | 依据 |
| --- | --- | --- |
| `--grip-thr` | 0.15 m | 夹爪在"待机"高度就是 0.1875 m，抬升后保持 0.26 m。0.15 稳稳低于待机高度，只用来排除夹爪压根没动的情况；真正的区分靠箱子那一项。 |
| `--lift-margin` | 5 mm | 箱子是 35 mm 立方体，静止中心高 0.0175 m。物理上它只有被带起来才会高出这个数；5 mm 大于位姿噪声（实测静止帧抖动 < 1e-6 m），小于任何一次真实抬升（≥ 60 mm）。 |
| `--period` | 0.100 s | **不是拟合出来的，是后端写死的**：teleport carry 每 0.1 s pin 一次。这一项的意义是"把测到的周期拿去和已知的机制周期对表"，周期对上了才说明锯齿来自 pin，而不是别的东西。 |
| `--period-tol` | ±0.030 s | 50 Hz 采样下周期分辨率是 20 ms；±30 ms 容得下 1~2 帧的极值定位抖动，又远小于 pin 周期本身，不会把 0.2 s 的二次谐波（±100 ms）认进来。 |
| `--pp-thr` | 30 mm | 取的是"明显不是刚性跟随"的量级：箱子半高才 17.5 mm，单周期掉 30 mm 意味着它清晰地脱开又回来。同时它远低于实测的 ~70 mm，留足裕度。 |
| `--offset-tol` | 5 mm | 刚性跟随的判据是"delta **变化**小"，不是"delta 小"。箱子被夹在爪子下方 40 mm 也是完全正常的刚性跟随（探针实测刚性误差 0.0000 m）。5 mm 远大于正常接触抖动，又远小于锯齿的 ~70 mm。 |
| `--gap` | 3 帧 | 锯齿波谷只有 1~2 帧低于 margin，3 帧足够连上，又不至于把两次独立抓取粘成一段。 |
| `--hold-speed` | 0.05 m/s | 夹爪抬升时速度约 0.5 m/s，保持时实测 < 1e-5 m/s。0.05 落在两者之间空档的正中间。 |

---

## 离线验证（真实数据，2026-10-27）

数据来自 `setup/acceptance/local_run_20261027/`，栈未启动，纯离线读文件。

### poses4.jsonl.gz（运行 B，四轮，7372 帧 / 147 s）

```bash
$ python3 setup/114_carry_watch.py --poses setup/acceptance/local_run_20261027/poses4.jsonl.gz
=== carry watch ===
来源        : setup/acceptance/local_run_20261027/poses4.jsonl.gz
模型        : box=target_box_a  gripper=gripper_left_link+gripper_right_link
总帧数      : 7372   静止高度 box_z=0.0175 m
抬升段      : 4 段
   [ 1064, 1298)  234 帧  4.650 s  t=[32.205, 36.855]
   [ 3241, 3389)  148 帧  2.940 s  t=[75.630, 78.570]
   [ 5168, 5406)  238 帧  4.735 s  t=[114.100, 118.835] <== 取这段
   [ 7340, 7372)   32 帧  0.620 s  t=[157.465, 158.085]

分析窗口    : hold  [5200, 5359)
时长 / 帧数 : 3.155 s / 159 帧   采样率 50.1 Hz
delta       : min 0.1426  max 0.2528  mean 0.1847  峰峰 110.2 mm
局部极值    : 极小 31 个 / 极大 31 个
平均周期    : 0.1005 s  （30 个极小间距的均值）
单周期峰峰  : 70.6 mm  （30 个周期的均值）

判定        : SAWTOOTH
理由        : delta 有 31 个局部极小，平均周期 0.1005 s（pin 周期 0.100 s ±0.030），单周期峰峰 70.6 mm > 30.0 mm：箱子每 0.100 s 被瞬移一次，其余时间在掉落。
```

四轮抓取出四段抬升，与运行 B 的 4 次 trial 对上。

### poses.jsonl.gz（运行 A，单轮，2208 帧 / 44 s）

```bash
$ python3 setup/114_carry_watch.py --poses setup/acceptance/local_run_20261027/poses.jsonl.gz
=== carry watch ===
来源        : setup/acceptance/local_run_20261027/poses.jsonl.gz
模型        : box=target_box_a  gripper=gripper_left_link+gripper_right_link
总帧数      : 2208   静止高度 box_z=0.0175 m
抬升段      : 1 段
   [ 1066, 1305)  239 帧  4.745 s  t=[32.010, 36.755] <== 取这段

分析窗口    : hold  [1095, 1259)
时长 / 帧数 : 3.250 s / 164 帧   采样率 50.2 Hz
delta       : min 0.1435  max 0.2585  mean 0.1869  峰峰 115.0 mm
局部极值    : 极小 32 个 / 极大 33 个
平均周期    : 0.1003 s  （31 个极小间距的均值）
单周期峰峰  : 69.9 mm  （32 个周期的均值）

判定        : SAWTOOTH
理由        : delta 有 32 个局部极小，平均周期 0.1003 s（pin 周期 0.100 s ±0.030），单周期峰峰 69.9 mm > 30.0 mm：箱子每 0.100 s 被瞬移一次，其余时间在掉落。
```

### 汇总

| 文件 | 轮数 | 判定 | 平均周期 | 单周期峰峰 | delta 峰峰（全局） |
| --- | --- | --- | --- | --- | --- |
| `poses4.jsonl.gz` | 4 | **SAWTOOTH** | 0.1005 s | 70.6 mm | 110.2 mm |
| `poses.jsonl.gz` | 1 | **SAWTOOTH** | 0.1003 s | 69.9 mm | 115.0 mm |
| `demo_poses.jsonl.gz` | 1（demo） | **SAWTOOTH** | 0.1009 s | 67.6 mm | 117.3 mm |

三份真实数据一致判出 `SAWTOOTH`，周期 **0.1003 ~ 0.1009 s**（≈0.101 s ✓），
单周期峰峰 **67.6 ~ 70.6 mm**（≈67 mm ✓，与报告里手工测的 0.0673 m 同一量级）。

单周期峰峰在 67.6 ~ 70.6 之间浮动，是**分析窗口口径**造成的，不是噪声：
保持段取得宽一点就会带进波谷更深的边缘周期。报告中 0.0673 m 那次的手工窗口
最接近 `demo_poses` 的口径。判定时用的是 > 30 mm，这个 3 mm 的浮动不影响任何结论。

### 三个分支都验过

除真实数据外，用合成数据（帧比例照抄真实数据：箱子绝大多数时间躺在桌上）验了另外两个分支：

| 场景 | 判定 | 关键数字 |
| --- | --- | --- |
| 刚性跟随，恒定偏移 40 mm + 0.4 mm 抖动 | `CONSTANT_OFFSET` | delta 峰峰 0.8 mm < 5 mm |
| 夹爪照常抬升、箱子全程躺桌上 | `NO_CARRY` | 箱子仅高出静止 0.0 mm |
| 位姿流里没有夹爪模型 | — | 退出码 2 |
| 文件不存在 | — | 退出码 2 |

---

## 换到刚性后端后，怎么用同一个工具确认

`docs/BACKEND_ADMISSION_20261027.md` 里 DetachableJoint 探针已在静态父体下 6/6 可用、
刚性误差 0.0000 m。接入之后，用**同一条命令、同一套阈值**重测：

```bash
# 1) 起栈、录位姿、停栈（必须在同一次 WSL 会话内）
bash setup/flexcell start
(timeout 150 gz topic -e -t /world/empty/dynamic_pose/info \
   -n 9000 --json-output > poses_rigid.jsonl &)
python3 setup/111_grasp_probe.py --object target_box_a --trials 4 --out A4_rigid.jsonl
bash setup/flexcell stop

# 2) 同一工具，不改任何阈值
python3 setup/114_carry_watch.py --poses poses_rigid.jsonl \
  --json evidence/carry_watch_rigid.json
```

### 期望看到什么

**后端真的修好了** → `CONSTANT_OFFSET`，大致长这样：

```
delta       : min 0.0396  max 0.0404  mean 0.0400  峰峰 0.8 mm
局部极值    : 极小 148 个 / 极大 149 个
平均周期    : 0.0400 s
单周期峰峰  : 0.8 mm
判定        : CONSTANT_OFFSET
理由        : delta 全程只变化 0.8 mm (< 5.0 mm)，且无周期性：箱子稳定跟随夹爪，只是差一个恒定偏移。
```

注意上例中"局部极小 148 个、周期 0.0400 s"是 0.4 mm 数值抖动造出来的伪极值 ——
**这恰恰说明判定不能只看"有没有周期性"**：周期对不上 0.1 s、峰峰也远低于 30 mm，
所以工具正确地走了 `CONSTANT_OFFSET` 分支。真正的刚性跟随下 delta 变化会收敛到
接触求解器的残差量级（亚毫米）。

**验收线**：`verdict == CONSTANT_OFFSET` 且 delta 峰峰 < 5 mm。

### 如果还是 SAWTOOTH

周期仍然 ≈0.100 s、峰峰仍然 ≈70 mm，说明换后端没生效，或者还有第二层原因：

- 先确认 carry 插件确实是 DetachableJoint 在跑，而不是 teleport 分支没被替换掉；
- 再看周期：如果周期不再是 0.1 s，那是**另一个**机制（比如接触求解器发散、关节软了），
  `--period` 要跟着改，别硬套 0.1；
- 若判成 `NO_CARRY` 且理由说"箱子没被带起来"，那是附着根本没建立，先查 attach/detach 的触发。

### 顺带能确认的第二件事

后端修好后，`rise` 的**方差**应该大幅收敛：同一个抓持不再因为采样相位而在
+0.08 和 −0.008 之间跳。这是 `CARRY_TELEPORT_20261027.md` 里"它是 #32/#13 的根因吗"
那一节的正面验证 —— 证实需要"绑定后箱子稳定跟随、rise 稳定为正且方差大幅收敛"两个条件同时成立。

---

## 限制

1. **只看 z，不看 x/y。** 本工具只判"垂直跟随"。箱子被拖着在水平面上滑但没被夹住的情况，
   z 上也可能看起来是 `CONSTANT_OFFSET`。要排除得另看水平相对位移。
2. **只看抬升 + 保持段。** 释放、放置段没做同样分析；`--lift-margin` 以上才算抬升。
3. **rest 用全程中位数。** 对"箱子大部分时间躺在桌上"的长录制（真实用法）没问题；
   如果录的只是 PICK 那一小段、箱子大部分时间在空中，中位数就不再是静止高度，
   要用 `--rest 0.0175` 显式给。
4. **50 Hz 采样，周期分辨率 20 ms。** 0.1 s 周期只有 ~5 个采样点，周期是均值估计，
   单点抖动 ±1 帧会让它晃 ±20 ms。峰峰同理会被"采样没踩到真正的波峰/波谷"略微低估。
5. **sim 时间没有和其他时钟对齐。** 时间戳直接取 gz 的 `header.stamp`，
   `--follow` 下也没有和 ROS 时钟做相位对齐。
6. **`--follow` 分支未在真机上跑过。** 本次验证全是离线（仿真额度有限、栈不能常驻），
   在线路径只做了代码级检查：它会起 `gz topic` 子进程、逐行解析、Ctrl-C 时正确收尾。
   首次在 WSL 里用 `--follow` 时应确认 `gz` 在 PATH 上、ROS/Gazebo 环境已 source。
7. **只验了一个物体（target_box_a）、一个 world（empty）、一台机器。**
   `target_box_b` 需要显式 `--box target_box_b`，但没跑过数据。
8. **判定的是"跟随质量"，不是抓取成败。** 它不能替代 `rise` 或任务级判定；
   它的作用是让人知道 `rise` 那个数字可不可信。
