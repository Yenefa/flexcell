# EvoBot 视觉观测采集通路（camera_snapshot + 配对 + 拒绝）

> **这是采集通路，不是感知。** 帧被写出、被与真值配对、没有帧时工具会拒绝而不是撒谎。
> 本文**不**声称图像被理解、物体被识别、或机器人"能看见"。

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-11 |
| 执行者 | skill-gap（teammate） |
| 仓库 | `project-033-flexcell/wt-comp` |
| 改验收器/TaskSpec/阈值 | **否**（`benchmark/evaluators/evaluate.py` 与 HEAD 逐字节相同，见 §6） |
| 改 `evobot_run_b.sh` | **否**（包装，不修改；见 §3） |
| 构建产物位置 | `/tmp/t08_iface`（隔离 overlay），**未写** `/home/ros/flexcell-p14-ws/install` |
| LLM 调用 | 0 |
| git commit | 无 |

---

## 0. 交付的四件东西

| # | 文件 | 作用 |
| --- | --- | --- |
| 1 | `wt-comp/src/flexcell/flexcell_skills/flexcell_skills/camera_snapshot.py` | 订阅 `/flexcell/camera/rgb`，写 PNG；**拿不到可用帧就非零退出** |
| 2 | `ci-public-window/scripts/evobot_capture_frames.sh` | `CAPTURE_FRAMES=1` 时在关键时点采集；**默认不改行为** |
| 3 | `ci-public-window/scripts/evobot_visual_vs_truth.py` | 每帧配一份同一时刻测的真值，产出 `visual_vs_truth.json` |
| 4 | `ci-public-window/scripts/evobot_vis_failure_probe.py` | 用合成 ROS 图像证明工具会拒绝（两个失败退出码） |

---

## 1. 为什么选 Pillow + numpy（而不是 cv_bridge）

实测环境：`numpy 1.26.4`、`Pillow 10.2.0`、`cv2 4.6.0`、`cv_bridge 4.1.0` **全都装了**。

仍然不用 cv_bridge：它多做一件本工具不需要的事（ROS↔OpenCV 转换），而**本工具需要的是拒绝**。
直接读 `sensor_msgs/Image` 的 `width/height/step/encoding/data` 让每一条拒绝条件都能写成
可单测的纯函数（`expected_bytes` / `check_buffer` / `uniformity` / `validate_frame`），
不需要启动 ROS 就能测。Pillow 只负责最后一步编码。

---

## 2. 拒绝规则与退出码（工具的核心）

| 退出码 | 常量 | 触发条件 |
| --- | --- | --- |
| 0 | `EXIT_OK` | 拿到合格帧并写出 PNG + sidecar |
| 1 | `EXIT_USAGE` | 参数错误 |
| **2** | `EXIT_NO_FRAME` | **超时内没有任何帧**（0 条消息） |
| **3** | `EXIT_BAD_FRAME` | **帧到达但不可用**：截断/超长/编码不支持/step 非法/几何非法 |
| **4** | `EXIT_UNIFORM` | **整帧每个字节相同**（渲染器什么都没产出时就是这样） |
| 5 | `EXIT_WRITE_FAILED` | PNG 或 sidecar 写失败 |
| 6 | `EXIT_INTERPRETER` | 解释器级异常 |
| 7 | `EXIT_STALE` | 帧的仿真时间戳早于请求的时点（排队帧） |

**每一条拒绝路径都：非零退出 + 不写图像文件。** 先写 `.partial` 再 `os.replace`，
所以半张 PNG 永远不会出现在目标路径上被后续步骤捡走。

两个设计要点，都不是随手写的：

- **为什么把"整帧均匀"当作拒绝**：全零缓冲正是"渲染器什么都没产出"交给你的东西，
  与一张真实的纯黑图片**无法区分**。要纯黑帧必须显式 `--allow-uniform`，且 sidecar 会记录。
- **为什么要 `--min-stamp-ns`**：没有它，一个"stage 2 之后"的采集可能拿到 stage 1 之前
  就在订阅队列里的帧——文件看起来正常，时间归属却是假的。

---

## 3. 采集时点（第 2 件）

`evobot_capture_frames.sh` 在 `CAPTURE_FRAMES=1` 时采：

| label | 时点 |
| --- | --- |
| `task_start` | 任何运动之前 |
| `stage_<n>` | 每个 composite stage 提交之后 |
| `failure` | 任何技能失败（读 baseline 自己写的 `verdict.json`，不重新判分） |
| `task_end` | 任务结束后、拆栈之前 |

**没有改 `evobot_run_b.sh`**：本脚本**包装**它（`evobot_run_b.sh ... &`），
baseline 走的是它自己的原文件。在它内部加分支会让"被测路径"和"改过的路径"是同一个文件。

**为什么 stage 钩子读 journal 而不是轮询日志**：composite journal 是 append-only 且每个事件
fsync，`COMMITTED` 行出现的确切时刻就是 stage 提交的时刻。轮询它不会漏一个 stage，
也不会凭空造一个；轮询 log tail 或 topic 两件事都可能发生。

`CAPTURE_FRAMES` 未设或不为 1 时：打印 `CAPTURE_DISABLED`，**退出 0，什么都不做**（实测见 §5）。

---

## 4. 配对（第 3 件）

`visual_vs_truth.json` 每条 pair 记录：

```
frame, label, png_sha256, png_bytes, width, height,
sim_stamp_ns, captured_wall_ns, truth_wall_ns,
pairing_gap_s, truth_source, objects{name: [x,y,z]}
```

**真值优先在采集进程内取**（`camera_snapshot.py --truth-objects`，帧落地后立刻
`sample_gz_pose`），所以 `pairing_gap_s` 是**测出来的**而不是事后重建的。

### 4b. z 高度序列 —— 这是判据必需输入，不是诊断附件

`evaluate.py` **v0.4.0**（lead 于 2026-11-11 修改）的 push 子句要求
`final_state['trajectory'][name]['max_z_m']`，**没有轨迹就判 False（fail closed）**。
原因：终态几何无法区分「推」和「抓起来搬过去放下」——两者终点相同。

所以配对产物现在额外输出：

| 文件 | 内容 |
| --- | --- |
| `visual_vs_truth.json` | 每帧配对 + `trajectory` 块 |
| `visual_vs_truth.json.trajectory.json` | **直接可并入 `final_state['trajectory']` 的形状** |

`trajectory[name]` 字段：

```json
{ "max_z_m": 0.0176, "min_z_m": 0.0175, "first_z_m": 0.0175,
  "last_z_m": 0.0175, "sample_count": 12, "max_sample_gap_s": 0.51,
  "source": "GZ_GROUND_TRUTH_SAMPLED",
  "limit": "max_z_m is the maximum over 12 sampled frames; motion that began
            and ended inside the widest 0.510s gap is not represented" }
```

**`limit` 字段是必须的**：`max_z_m` 是**采样帧上的**最大值，不是连续运动上的最大值。
两次采集之间完成的抬起-放下不会被看到。记录里写明采样数与最大间隔，
读的人才能判断「间隙里可能藏了多少运动」，而不是默认没有。

`test_visual_trajectory_clause.py` **直接 import 冻结的 evaluate.py** 验证：
- 没轨迹 → push 子句 False 且 `trajectory_required=True`（fail closed 成立）
- `max_z_m=0.12`（抓住搬走）→ False（v0.3.0 会误判 True 的那个 bug）
- 我们产出的形状 → **真实评测器判 True**（端到端兼容）
- 采到帧里的真实抬起 → `max_z_m` 如实反映
- 本卡**不重述**评测器阈值，只验证形状兼容。

三条不撒谎规则（都有单测）：

1. 最近真值样本超出 `--max-gap` → **不配对**，写进 `unpaired` 并带原因；
2. 没测到的物体 → **不出现**在 `objects` 里，绝不用默认值补齐；
3. 帧没有 `captured_wall_ns` → 拒绝配对。

产物自带 `scope` 字段，写明"配对只意味着真值在该帧附近 max_gap_s 内被测到，
**不**意味着图像被解释、被识别、或机器人能看见"——让单独捡到这个文件的人也读不错。

---

## 5. 证明它会失败（第 4 件，实测退出码）

```
bash ci-public-window/scripts/evobot_vis_failure_probe.py silent    --timeout 3
bash ci-public-window/scripts/evobot_vis_failure_probe.py truncated --timeout 6
bash ci-public-window/scripts/evobot_vis_failure_probe.py uniform   --timeout 6
bash ci-public-window/scripts/evobot_vis_failure_probe.py good      --timeout 6
```

| 模式 | 退出码 | 写了文件？ | 消息 |
| --- | --- | --- | --- |
| **silent**（topic 从不发布） | **2** | **否** | `no /flexcell/camera/rgb frame arrived within 3.0s (subscribed, 0 messages)` |
| **truncated**（9216 字节只要 9211） | **3** | **否** | `30 frame(s) arrived but none was usable; last refusal: expected 9216 bytes (64x48, step 192, rgb8) but the message carried 9211` |
| **uniform**（全零帧） | **4** | **否** | `every byte of the 64x48 rgb8 frame is 0 ... a renderer that produced nothing looks exactly like this` |
| good（阳性对照） | **0** | 是 | 64×48 PNG，9216 字节帧 |

**关键**：三个拒绝模式的退出码是 2/3/4，且 `ls` 证明**没有留下任何图像文件**。
阳性对照同时跑，证明拒绝不是因为工具根本不能用。

> 该探针用**合成 ROS 图像 + 手写 publisher**，不启动 Gazebo。理由：要证明的是"该拒绝时会拒绝"，
> 真渲染器不增加这条证据，而会在大批次旁边多开一个高负载 sim。

---

## 6. 冻结文件未被改动（逐字节验证）

```
git hash-object 与 git rev-parse HEAD:<path> 相同：
  benchmark/evaluators/evaluate.py                     same=True
  src/flexcell/flexcell_skills/flexcell_skills/pick_server.py  same=True
  src/flexcell/flexcell_skills/config/week1.yaml       same=True
```

`evobot_run_b.sh` 同样未改（本卡新增的是**新文件** `evobot_capture_frames.sh`）。

---

## 7. 测试

| 套件 | 数量 |
| --- | --- |
| `test_camera_snapshot.py` | 25 |
| `test_visual_truth_pairing.py` | 17 |
| `test_visual_trajectory_clause.py`（**跑真实 evaluate.py v0.4.0**） | 8 |
| `test_z_trajectory.py` | 10 |
| `test_camera_bridge.py` + `test_vision_geometry.py`（既有，回归） | 18 |
| **视觉相关合计** | **78 / 78 通过** |
| 全量技能套件（排除 4 个与本次无关的既有失败模块） | **1308 / 1308 通过** |

`test_camera_snapshot.py` 用**真实的 `sensor_msgs/Image` 对象**驱动 `accept_message`，
不是只对常量做断言。

---

## 8. 复现

```bash
# 单元测试
wsl -d Ubuntu-24.04 -- bash -c '
  source /opt/ros/jazzy/setup.bash
  cd /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
  PYTHONPATH=$PWD/src/flexcell/flexcell_skills:$PYTHONPATH     python3 -m pytest -q src/flexcell/flexcell_skills/test/test_camera_snapshot.py                       src/flexcell/flexcell_skills/test/test_visual_truth_pairing.py'

# 失败证明（无需 Gazebo）
bash ci-public-window/scripts/evobot_vis_failure_probe.py silent --timeout 3; echo "rc=$?"

# 真实采集（需空闲通道；脚本自己会拒绝在有 batch/gz sim 时启动）
bash ci-public-window/scripts/evobot_vis_live_capture.sh /tmp/vis_live 235
```

---

## 8b. 真实帧往返验证（不需要 Gazebo）

`ci-public-window/scripts/evobot_vis_roundtrip_real_frame.sh`

用归档的**真实 640×480 Gazebo 渲染帧**（`iyaic-release-sample/evidence/frames/frame_mid.png`，
其 README 明确写"真实渲染帧，非合成"），以真正的 `sensor_msgs/Image` (rgb8, step=1920)
发布到 `/flexcell/camera/rgb`，再用本卡的 `camera_snapshot.py` 采集回来：

```
capture_exit=0
captured 640x480 rgb8, 921600 bytes, sha256 9e3b2055...
a shape=(480, 640, 3)  b shape=(480, 640, 3)
max_abs_pixel_diff=0  differing_pixels=0 of 307200
ROUNDTRIP_IDENTICAL
```

**这证明了什么**：真实相机尺寸/内容经过完整解码路径后**逐像素相同**。
通道交换、行跨距错误、dtype 误解这些"看起来合理的错图"缺陷会立刻在这里暴露。

**这不证明什么**：不证明此刻有相机在发布——那只有真实 sim 能证明。

## 9. 明确不宣称

- 不宣称图像被**理解**、物体被**识别**、机器人**能看见**。
- 不宣称配对等于视觉判定正确——配对只把"该帧附近物体实际在哪"记下来，供以后核对。
- 不宣称任何 rung。本卡是采集通路：**Designed + Implemented + Unit Tested**；
  真实帧采集见 §10（若通道未取得则如实写明）。
- 不宣称成功率/重复性。

---

## 10. 真实帧采集（已在真实 Gazebo 上完成）

### 10.1 环境与阻塞

批次 `baseline_a_v2_gated_20261111` 期间**未抢通道**。轮询时发现批次卡在 68/72，
诊断出**每实例泄漏 1 个 `parameter_bridge` + 1 个 `robot_state_publisher`**
（68 实例 = 136 进程 = 227% CPU），把 `loadavg` 顶到 3.7~5.7，超过批次的
`LOAD_CEIL=3.0`，4 个实例即将被记 `INVALID_INFRA`。已上报 lead，lead 亲自 reap。
reap 后 `load_after` 从 **19.89 掉到 2.28**，批次收敛到 **72/72，0 个 INVALID_INFRA**。

lead 用这段数据做的分桶结论（记在本卡名下）：
`load_after <5 → 25/25`、`5-10 → 27/27`、`10-15 → 13/14`、`>=15 → 6/6`，
最高负载组 100% —— **泄漏污染了机器，没有污染结果变量，A-v2 不用重跑**。

### 10.2 真实帧

| 项 | 值 |
| --- | --- |
| 路径 | `frames/real_gazebo_frame.png` |
| 尺寸 | **640×480** RGB，921600 字节帧，**22939 字节 PNG** |
| sha256(帧) | `447ad1dad00a7409b3dc690225a301d88f0ce09c0ee676a9ed52e575456aa3f6` |
| frame_id | `dataset_camera/camera_link/rgb` |
| 内容 | 机械臂 + 红色 `target_box_a` + 蓝色 `target_box_b` + 两个区域标记 |
| 真值（同刻） | `target_box_a=[0.22,0,0.0175]`、`target_box_b=[0.2,-0.18,0.0175]` |

**时序说明（重要）**：帧的 `stamp_ns=148900000000` 是仿真时间（gz 从 0 起算），
真值用 `time.time_ns()`。两者**不是同一个时钟**，所以配对记录的是**墙钟间隙**
`pairing_gap_s`，而不是假装它们可以相减。本例间隙 ~0.07 s。

### 10.3 z 高度序列（判据必需输入）

```
10 s @ 20 Hz，实测 achieved_hz = 20.002 / 20.003
sample_count = 191 / object（共 382 次采样）
max_z_m = 0.0175  min_z_m = 0.0175  spread = 0.000000
max_sample_gap_s = 0.0546   max_sample_age_s = 0.0845
```

产出两个文件：
- `final_state.json` —— **直接喂 `evaluate.py`**：`{objects, trajectory}`
- `z_series.json` —— 采样序列（本卡归档为裁剪版）

### 10.4 冻结评测器实测接受（v0.4.0）

用本卡产出的 `final_state.json`（真值 + 191 点轨迹），把终态位移设为真实 30 mm 推：

```
evaluator_version: 0.4.0
passed: True   failed: []
push:target_box_a -> True
  displacement_m=0.03  vertical_m=0.0  direction_cosine=1.0
```

**这是"本卡产物满足 v0.4.0 判据"的实测证据**，不是推断。

### 10.5 一个诚实的说明：本次采的是**静止 z**

机械臂**没有动**。所以 `max_z = min_z = 0.0175`，即物体在桌上的静止高度。
这是一个**推之前的基线**，不是一次真实推动的轨迹。
真实 T08 推动时的 z 序列，要等 T08 链跑起来才能采到——
但那需要跑到 push 技能，超出"camera-only 不跑任务"的窗口。

**因此**：本卡证明的是**采集通路能产出判据要求的输入**，
未证明"某次真实推的 max_z 判过了"。后者要等 T08 链。

### 10.6 采集中自己抓到的 2 个 bug

1. `ROS_DOMAIN_ID=235` → CycloneDDS 端口越界，**整个栈每个节点都
   `error creating node: error not set`**。已改到 45/46。
2. `PAIR="$W/ci-public-window/..."` —— `$W` 是 `wt-comp`，
   `ci-public-window` 是它的**兄弟目录**不是子目录，路径不存在导致**配对静默失败**
   而采集成功。已改为独立的 `$CI` 变量。

这两个都是"看起来对、跑起来错"的类型，靠真实运行才发现。
