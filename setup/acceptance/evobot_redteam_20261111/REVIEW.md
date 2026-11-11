# LIBERO 接入工作 红队复审（零上下文，只读）

审计对象：分支 `autonomous/flexcell-remediation`，提交 73756061..8e1ba83b，以及
`setup/acceptance/evobot_libero_*_20261111/` 下 9 个证据目录。
审计者：red-team（无先验上下文，不采信 commit message 与 README）。
审计时工作树：仅两个未跟踪目录（本目录 + 队友的 `evobot_tall_bottles_20261111`），
被审计的 9 个目录与 HEAD 一致（`git diff --stat` 为空）。

我做了什么：

1. 读完 9 个目录的 README / verify.py / 全部 JSON / 全部 runner 源码；
2. 用 `falsify_harness.py` 做**变异测试**：复制每个目录到临时副本，篡改 JSON / 日志，
   再跑 verify.py 看退出码，共 36 例，原始输出见 `FALSIFICATION.log`；
3. 独立复算每个 README 的数字（没有从 README 抄任何数）；
4. 用 `git log/show/diff` 与 `git status` 还原改动顺序与工作树状态；
5. 对着 LIBERO 上游克隆（`/mnt/c/.../ext-bench/LIBERO`，HEAD 8f1084e3，`git status` 干净）
   核对 BDDL、init 文件、check_success 实现、官方评估协议、以及每个物体资产的真实几何。

我**没有**做：没有跑任何仿真、没有跑机器人、没有执行任何 runner（按任务要求）。
因此本报告能判定的只有两类事实：(a) 落盘产物内部是否自洽；(b) 落盘代码能否产生所声称的实验。
"这些数是不是真跑出来的"我无法用执行验证，只能看证据链——而证据链本身出了问题（见 B1）。

---

## 0. 结论摘要

**不是干净的报告。** 先说公允的部分：9 个 verify.py 是**真实的转录一致性检查**（改数字会挂，§1），
比常见的"永不失败的 verifier"好；OFFICIAL 分类在"环境/任务/判据来自上游且未被改动"这层**站得住**（§2.1）；
多数 README 数字能复算；而且每轮都主动写了"不宣称"清单，有些（如 side_grasp 的"并集不是成绩"）是本项目里最诚实的部分。

但有两处是**根本性的**，且都在最后三轮的核心结论上：

| # | 严重度 | 一句话 |
| --- | --- | --- |
| B1 | **blocker** | "三个抓取比例（0.50/0.85/0.70）结果相同 → 高度不是杠杆"这个否证，**在落盘代码里比例根本不进控制环**（`grasp_z(0.5)` 硬编码）；JSON 自己写着 top 臂 target=0.015；且 `mid_*.json` 的日志格式与落盘 runner 生成的不一致，**这批产物不是这个脚本产生的**；0.70 那组**没有任何产物** |
| B2 | **blocker** | "几何推导抓取"实际算的是 `geom_xpos ± geom_rbound`，即**包围球半径**，不是几何 z 范围。在 libero_spatial 上，这个"高度"是被测物真实高度的 **2.6 倍**，抓取目标落在碗顶面**上方 4.8–13.9 cm**——这才是 0/10 的机制，而不是 README 说的"碗的形状不同 / 这套策略不适合该套件" |
| B3 | major | "释放误差 ≤10mm 成功 / >300mm 失败、差两个数量级"这个"失败检测器"被**同一批产物里的 60mm/98mm 载物失败**否定 |
| B4 | major | solved 轮的两个"实验定位"数字（basket_1_main z=0.035 / contain_region z=0.1068）**没有任何产物支持**，且 result.json 同一行写的是 0.107（日志标签贴错） |
| B5 | major | "这轮没有任何拟合常数"是错的：`LIFT_PROOF_M=0.03` 等常数仍在，且这个 0.03 正是上一轮在同一套件上标定出来的数 |
| B6 | major | 留出套件 libero_spatial 在 0/10 之后被用来**设计**下一版控制器，然后又用同一套件报告"留出 0/10"——它已经不是留出集 |
| B7 | major | "OFFICIAL 任务完成"的分母是 **50 个官方 init 状态里的第 0 个、1 个 episode**；官方协议是 20 episode 的成功率。README 没写 n |
| B8 | major | "INDEPENDENTLY_VERIFIED" 不成立：verify.py 只读已落盘 JSON，从不重跑实验；仓库自己把该 rung 定义成"独立 evaluator 通过" |
| B9 | major | side_grasp 的 verify.py 有一行 `assert ... or True`，**永不失败**；清空 5 个日志仍 exit 0 |
| B10 | major | auto_approach 对 side_y 的"否证"只写在打印字符串里，无任何断言；删掉两个 JSON 或改成成功，verify.py 仍 exit 0 |
| m8 | minor | "0/10 留出"里那 10 个任务**共用同一个物体**（akita_black_bowl_1 → plate_1），所以它是 1 个物体 × 10 个初始位姿，不是 10 个不同物体的泛化检验 |
| m1–m7 | minor | 若干数字与 JSON 不符 / 跨臂引用 / 跨集合比较 / 封条无意义 / 不可观测指标等，§3 |

---

## 1. Q1：verify.py 真的会失败吗？（变异测试）

**答案：会失败，但只对少量字段；有若干"声称"根本不进断言。** 完整 36 例见 `FALSIFICATION.log`。
（日志里 3 个 `<== interesting` 是我预期标签写反了，实际是**正确失败**，不是问题。）

### 1.1 能失败的（真实检查）

| 目录 | 变异 | 结果 |
| --- | --- | --- |
| official | action_dim 7→6 | exit 1 |
| official | `official_success_with_noop_policy` false→true | exit 1 |
| official | `init_note` "official init state loaded"→"not used" | exit 1 |
| solved | `official_success` true→false | exit 1 |
| solved | 物体 final 改回起点（说"没动"） | exit 1 |
| solved | 删掉 calibration 的 `lift_above_control` | exit 1 |
| transfer | t1 失败→成功 | exit 1 |
| transfer | `parsed_region` 去掉 `_contain_region` | exit 1 |
| geometry | mid_2 失败→成功 | exit 1 |
| geometry | 删掉全部 top_*.json | exit 1 |
| side | side_1 成功→失败 | exit 1 |
| side | 成功样本的 release error 0.0041→0.5 | exit 1 |
| auto | auto_3 成功→失败 | exit 1 |
| auto | clamped 臂人为改成 5/5 | exit 1 |
| auto | auto_3 的 `mode` 改成 top | exit 1 |
| holdout | s0 成功→true | exit 1 |
| holdout | s0 mode→top | exit 1 |
| holdout | s0 release error 0.48→0.05 | exit 1 |
| closed-loop | obj_3 成功→false | exit 1 |
| closed-loop | obj_3 删掉第二次尝试 | exit 1 |
| closed-loop | spa_0 声称 `carried=True` | exit 1 |

所以"verifier 全是摆设"**不成立**——改结论数字确实会挂。这是要记给作者的正面一条。

### 1.2 不能失败的（这才是问题）

| # | 位置 | 做法 | 结果 | 说明 |
| --- | --- | --- | --- | --- |
| F1 | `side_grasp/verify.py:30-31` | 5 个 side_*.json 的 `log` 全清空 | **exit 0** | `assert "episode terminated" in ... or True` —— `X or True` 恒真，**这一行不可能失败**。它对应的正是 README:34-38 自曝的 harness bug，即那次披露的唯一机器检查是空的 |
| F2 | `auto_approach/verify.py:32-46` | 删除 `side_y_2.json` / `side_y_4.json` | **exit 0** | 改成 `official_success=true, release_xy_error_m=0` 也 exit 0。"side_y 仍失败（504/651mm）"只存在于打印的 dict 字面量里，**没有任何 assert 读那两个文件** |
| F3 | `geometry_grasp/verify.py:41` | 给 top_0.json 加 `frac: 0.70` | **exit 0** | 全仓库 grep `0.70` 只命中 `README.md:26` 与 `verify.py:41`，**没有任何 0.70 的产物**，verifier 也不检查比例是否真的变过 |
| F4 | `holdout_spatial/verify.py` | s0 日志 `measured height 0.168` → 0.090 | **exit 0** | "测得高度 vs 阈值"这个关键中间量完全不受检查（而 B2 说明它正是错的） |
| F5 | `official/verify.py:44-47` | `run_result.json` 的 `stepped` 5→999 | **exit 0** | 步数不检查；只查 action_dim / init_note / noop 三个字段 |
| F6 | `solved/verify.py` | result.json:10 的 `basket_1_main ... 0.107` → `0.035` | **exit 0** | 见 B4 |
| F7 | `transfer/verify.py:25-28` | t1 日志改成"物体被搬起来了" | **exit 0** | 对失败任务只断言最后一行含 `object final at`；机制描述不受检查 |
| F8 | `closed_loop_retry/verify.py:24-28` | obj_2 两次尝试都改成 `carried=true` | **exit 0** | 只检查 obj_3 的重试 |

**更根本的一层：没有任何 verify.py 重跑实验。** 9 个 verify.py 全部只 `json.load` 已落盘文件
（唯一外部调用是 `official/verify.py:25` 的 `git log` 校验克隆 commit）。
没有一处调用 runner，没有一处记录运行命令、环境变量（`LIBERO_SUITE` / `LIBERO_TASK` / `MODE` / `MUJOCO_GL`）、
解释器路径或时间戳。全部 runner 的参数只能从源码反推。
所以 verify.py 证明的是"**转录**没被改"，不是"**实验**发生过"。
而 B1 说明：至少 geometry 那一轮的 JSON **不可能**由落盘的同名脚本产生。

> **什么会推翻我这一节**：给出任何一个 verify.py 会调用 runner 并用同参数重算 JSON 的版本；
> 或证明 F1–F8 上任一变异其实会让某个我没跑到的路径失败。

---

## 2. Q4 先答：OFFICIAL 这个分类站得住吗

**基本站得住。** 逐项核对：

| 项 | 结论 | 证据 |
| --- | --- | --- |
| 上游克隆未被改动 | 是 | `git status --porcelain` 输出为空；HEAD = `8f1084e3132a39270c3a13ebe37270a43ece2a01`（2025-03-15），与 `benchmark_meta.json:4` 一致 |
| 任务文件是上游 BDDL | 是 | `libero_object/pick_up_the_alphabet_soup_and_place_it_in_the_basket.bddl` 的 `(:goal (And (In alphabet_soup_1 basket_1_contain_region)))` 是上游原文；`(:objects ...)` 的 7 个物体、`(:init ...)` 的 region 绑定都在 |
| init 状态是官方 `.pruned_init` | 是（但只用第 0 个） | 见 B7 |
| 成功判据是官方谓词 | 是 | `env.check_success()` → `env_wrapper.py:103-104` 的 `return self.env._check_success()`；9 个目录无任何 monkeypatch（grep `_check_success` 只命中 `region_probe.py:30` 读 docstring，不参与评分） |
| 运行环境与元数据一致 | 是 | `/home/ros/ext-bench/venv-libero`：robosuite 1.4.1、mujoco 3.2.7、torch 2.15.0+cpu，与 `benchmark_meta.json:26` 一致 |
| 评分是否被 EvoBot 侧影响 | **否** | 判据只由 LIBERO 的谓语决定；EvoBot 侧只提供动作。但要说明：策略读的是**仿真器真值**（ORACLE，已在每份 README 声明），并且"目标区域"直接取的是判据所使用的那个 site（见 B2 的相关说明） |

**结论**：说"这是官方环境/官方任务/官方判据"没问题；说"完成了官方基准任务"就有分母问题（B7）。

---

## 3. 逐条问题

### B1（blocker）"三个抓取比例结果相同"这个实验在落盘代码里根本不存在

**主张**（`geometry_grasp/README.md:20-28`）："中点(0.5) 2/5 / 0.85 2/5 / 0.70 2/5 —— **三个比例结果完全相同**
→ 说明剩下三个失败**不是高度问题**"。commit 9998e225、`verify.py:41`（`height_is_not_the_lever`）、
`evidence_index.py:94` 的 rung 文本都复述这个结论。

**证据一（代码层）**：`geom_runner.py` 里 `FRAC` 只出现在三处——`:22` 读环境变量、`:111-112` 日志字符串、
`:145` /:150` 写 JSON 的 `grasp_z` 字段。真正的控制目标是**硬编码**的：

```python
113:    target_grasp = np.array([centre[0], centre[1], grasp_z(0.5)])
116:    drive(target_grasp, GRIP_OPEN, tol=0.008,
117:          stop=lambda c: (np.hypot(c[0] - centre[0], c[1] - centre[1]) < 0.012
118:                          and c[2] < grasp_z(0.75)))
120:    log.append("descended to eef z %.3f (target %.3f)" % (z_at, grasp_z(0.5)))
```

无论 `GRASP_FRAC` 设成 0.50 / 0.70 / 0.85，这个脚本都会瞄准 0.5 中点、在 0.75 处停止、
日志里打印 0.5 的 target；只有 JSON 里那个 `grasp_z` 数字会变。

**证据二（数据层）**：`top_*.json`（0.85 臂）的日志 `descended to eef z ... (target 0.015 / -0.000 / 0.024 / 0.027 / 0.024)`
与 `mid_*.json` **完全相同**；若真按 0.85 下探，target 应该是 `0.061 / 0.033 / 0.089 / 0.077 / 0.090`。
任务 0/1/2 的 descend 终点、位移、carried、final **逐位相同**；任务 3 除 final 外全同。
最直接的一行：`top_0.json` 第 3 条日志 `descended to eef z 0.043 (target 0.015)`，
而同文件记录的 `grasp_z` 是 `0.0609` —— **同一份文件里 target 与声称的抓取高度互相矛盾**。

**证据三（溯源层）**：`mid_*.json` 的日志写的是
`object extent z -0.051..0.081 -> grasp at 0.015 (midpoint)`，
而落盘的 `geom_runner.py:111-112` 生成的字符串是
`... -> grasp at %.3f (frac %.2f of the measured extent)`（`top_*.json` 正是这个格式）。
全仓库 grep `midpoint` 只命中 `verify.py:41`，**没有任何代码会打印 "(midpoint)"**。
所以 `mid_*.json` **不是落盘的 `geom_runner.py` 产生的**（它来自一个更早的、格式不同的版本），
而这批文件正是"2/5"与"三个比例"结论的唯一数据来源。

**证据四**：README:26 的 "0.70 → 2/5" 在全仓库**没有任何产物**。

**因此**以下三者必有其一为真，而三者都推翻 README 的结论：
(a) 这三个比例从未真正作用于控制器 → 结论无意义；
(b) `geom_runner.py` 不是产生 `mid_*.json` 的脚本 → 该轮产物失去 provenance；
(c) 两个臂用的是不同版本的脚本，且其中至少一个的比例没有生效。
"高度不是杠杆"在这条链上不成立，而它是后续三轮（side grasp、auto、retry）设计的前提之一。

> **什么会推翻我**：给出 `grasp_z(FRAC)` 出现在 :113 的 runner 版本（git blob / 另一份工作副本 / 原始运行日志），
> 且该版本的日志格式能生成 `mid_*.json` 的 "(midpoint)" 行；
> 或给出 top 臂日志里 target=0.061 而 eef 到位的记录；或给出任何 0.70 臂的 JSON。

---

### B2（blocker）"几何推导抓取"实际算的是包围球半径；0/10 的真正机制是抓取点悬在物体上方

这一条同时解释了两个轮次的结论为什么错，所以单独列出。

**代码事实**（`geom_runner.py:94-113`，`auto_runner.py:94-102`，`runner.py:104-112`，`retry_controller.py:88-95`
四处**同一段**）：

```python
for g in range(sim.model.ngeom):
    if sim.model.geom_bodyid[g] == bid:
        c = sim.data.geom_xpos[g]          # 几何体中心（世界系）
        rb = float(sim.model.geom_rbound[g])   # 包围球半径
        zs.append((c[2] - rb, c[2] + rb))      # 上下各加一个球半径
z_lo, z_hi = min(...), max(...)
gz = z_lo + FRAC * (z_hi - z_lo)
```

`geom_rbound` 是**包围球半径**，所以 `z_hi - z_lo` 是一个**球直径的 z 投影**，
不是物体的 z 尺寸。README 把它描述成"该 body 所有 geom 的 z 范围"（`auto_approach/README.md:16-18`），
这个描述与代码不符。

**可验证的后果一（libero_object）**：用上游资产 XML 的真实碰撞盒 z 跨度比对被测高度：

| 物体 | 资产 XML 碰撞盒真实高度 | 代码"测得高度" | 比值 |
| --- | --- | --- | --- |
| alphabet_soup | 0.1336 m | 0.131 | 0.98× |
| cream_cheese | 0.1015 m | 0.096 | 0.95× |
| salad_dressing | 0.0658 m | 0.187 | **2.84×** |
| bbq_sauce | 0.1071 m | 0.144 | 1.34× |
| ketchup | 0.0693 m | 0.187 | **2.70×** |

也就是说：细长瓶的"高度"被放大近 3 倍。**0.140 这个阈值是在这个被放大的量上选的**，
所以"高度 > 0.140 走侧向"实际是在区分"包围球大的物体"，不是"高的物体"。
两个高瓶（0.187）被判为"最高"，其实它们的真实高度只有 ~0.066–0.069 m。

**可验证的后果二（libero_spatial，0/10 的真正机制）**：
用 `akita_black_bowl.xml` 的碰撞盒（局部 z 跨度 −0.0120..0.0524，真实高度 **0.0644 m**）
与 `s*.json` 里记录的物体原点 z 比较：

| 任务 | 抓取 target z | 物体原点 z | 物体真实顶面 z | **target − 顶面** |
| --- | --- | --- | --- | --- |
| 0 | 0.998 | 0.898 | 0.950 | **+4.8 cm** |
| 3 | 1.108 | 0.917 | 0.969 | **+13.9 cm** |
| 4 | 1.179 | 1.063 | 1.115 | **+6.4 cm** |
| 9 | 1.260 | 1.126 | 1.178 | **+8.2 cm** |

10 个任务**全部**如此，间隙 4.8–13.9 cm。而 "测得高度" 在这 10 个任务上**恒为 0.168**
（真实高度 0.0644 的 **2.6 倍**）——因为包围球把横向半径也算进了竖直跨度。

**所以 0/10 的机制是：夹爪被命令合拢在碗顶面上方 5–14 cm 的空气中。**
这与 README 给出的解释不同：

- `holdout/README.md:56-57` 说 "两个套件的物体**几何分布不同**（libero_object 是罐头/瓶/盒，libero_spatial 是碗/盘），
  说明用高度阈值选策略这种一维规则不可能覆盖形状差异" —— 但真正发生的是**测量量本身错了**，
  而不是"形状差异无法用一维规则覆盖"；
- `closed_loop/README.md:36-39` 说 "不是选错，是**两种方式都抓不住碗**" —— 也不准确：
  两种方式**都没有碰到碗**，因为两者的抓取 z 都由同一个错误公式产生
  （`retry_controller.py:95` 一处计算，`:109` 与 `:112-119` 两种模式共用）。

**为什么这条重要**：最后三轮的核心叙事是"留出失败 → 定位到更深一层的抓取能力缺失 → 用测量反馈替代拟合"。
但证据显示失败点在**几何测量公式**这一行代码，它既不是"策略选择"，也不是"抓取能力"，
更不是需要"学习"的东西。把它归类成能力缺失，会让下一步去做错误的事（见 B6）。

> **什么会推翻我**：
> (a) `geom_rbound` 在该 MuJoCo 版本里不是包围球半径（若是，请给出定义与出处）；
> (b) 用同一脚本在同一 init 状态上重跑，实际抓取 z 与物体真实顶面的关系不是上表；
> (c) `akita_black_bowl.xml` 的碰撞盒不是抓取时生效的几何（例如实际用了别的资产/缩放）。

---

### B3（major）"两数量级"的失败检测器被同一批产物否定

**主张**（`side_grasp/README.md:30-32`）："成功的两个是 4.1mm / 3.7mm，失败的三个是 373 / 551 / 575mm，
**差两个数量级** —— 说明失败不是'松爪早了'，而是**夹爪根本没拿住，物体被推飞了**。这条校验同时是一个**可用的失败检测器**。"
commit d60b5d7c 与 af2386f2 都把它当作既定规则使用。

**反例（同一批产物，隔壁目录）**：

| 文件 | 物体抬升 | 释放误差 | official_success |
| --- | --- | --- | --- |
| `auto_approach/clamped_3.json` | `object after lift: [0.044, -0.092, 0.187]`（抬升约 0.16 m） | **0.09827 m = 98 mm** | false |
| `auto_approach/clamped_4.json` | `object after lift: [-0.111, -0.25, 0.204]`（抬升约 0.18 m） | **0.06012 m = 60 mm** | false |

这两次是**抓起来了但放偏了**的失败，落在 60–98 mm，与"成功 ≤10 mm"只差 6–10 倍，不是两个数量级。
`clamped_3.json` 的三次 re-approach 误差还在变化（0.0274 → 0.0819 → 0.0983），说明物体确实跟着夹爪走。
所以"释放误差 >100 mm ⇒ 根本没拿住"这个二分法在项目自己的数据里有 **60–98 mm 的灰区，且灰区里是载物失败**。

**它污染的结论**：`holdout/README.md:18-19` 与 commit af2386f2 用这条规则把 0/10 解释成
"不是放偏、是被接近动作推飞"；而 `closed_loop/README.md:36-44` 又改写成"两种方式都抓不住碗"。
两轮给出两个互不相同的机制，第一个机制的**唯一测量依据**就是这条被否定的规则。

**附带的反证（对"被推飞"不利）**：留出轮 s1–s9 的 `object after lift` 与 `object final` **逐位相同**
（例 `s1.json` 均为 `[-0.195, 0.315, 0.898]`），且 4 次 release attempt 的误差完全相同
（`s1.json:14-17` 都是 0.2935）。即这 10 次里有 **9 次**，物体在 "lift 之后到 episode 结束" 之间**没被碰过**；
"release error 119–480 mm" 在这个区间里等于"物体原位到目标点的距离"，对"被推飞"和"从没被碰"**没有区分力**。

> **什么会推翻我**：给出一次 `carried=True` 且 `release_err>0.3` 的运行（则分离成立）；
> 或证明 clamped_3/4 的物体其实没被夹爪带走；或给出留出轮每次尝试之间的物体位置记录，证明接近阶段确实推动了物体。

---

### B4（major）solved 轮的两个"实验定位"数字没有产物支持，日志标签还贴错了

**主张**（`solved/README.md:26-33` + commit 4ee25e67）："basket_1_main 0.035 vs
basket_1_contain_region 0.1068 → 改瞄官方 region 后物体入篮"。

**证据**：

1. `0.1068` 在整个仓库只出现在 `solved/README.md:31` 与 `solved/verify.py:40`（后者是硬编码打印字符串）；
   `0.035` 作为"basket 位置"只出现在 `README.md:30`。**没有任何 probe 输出文件** ——
   `region_probe.py` 存在，但它 `print` 到 stdout，输出未存档（对比：`calibration.json` 是存档的）。
2. 唯一记录 `basket_1_main` 位置的产物是 `solved/result.json:10`：
   `target basket_1_main at [0.015, 0.252, 0.107]` —— z 是 **0.107**，不是 0.035。
3. 原因是代码 bug（`solved/adapter_control.py:99-105`）：

```python
 99:    d = pos(dst_name)                              # basket_1_main
100:    region_site = dst_name.replace("_main", "") + "_contain_region"
101:    if region_site in list(sim.model.site_names):
102:        d = np.array(sim.data.site_xpos[...])       # d 被覆盖成 contain_region
103:        log.append("goal region %s at %s" % (region_site, np.round(d, 3).tolist()))
105:    log.append("target %s at %s" % (dst_name, np.round(d, 3).tolist()))  # 仍叫 basket_1_main
```

   这一行**永远**打印 contain_region 的位置却标成 basket_1_main，既不能支持 0.035，也不能支持 0.1068。
4. 变异测试（F6）：把这一行的 0.107 改成 0.035，`verify.py` **仍然 exit 0**；
   `verify.py:40` 又把这个数字写进自己的 verdict，形成闭环自证。

**为什么算 major**：这是本轮 README 明确标为"两个根因，都是实验定位的，不是猜的"的其中之一，
而它的两个数字在产物里都不存在，唯一的日志行还是错标签：`result.json:10` 与 `README.md:30` 直接冲突。

> **什么会推翻我**：存档 `region_probe.py` 的真实输出（显示 basket_1_main≈0.035 且 contain_region≈0.1068），
> 或给出修正标签后的重跑日志，其中两行分别打印 0.035 与 0.1068。

---

### B5（major）"这轮没有任何拟合常数"是错的

**主张**：`closed_loop/README.md:25` "这轮没有任何拟合常数"、`:51` "3/5，**无拟合常数**"、
`verify.py:37` 的 `3/5, no fitted constant`、commit 8e1ba83b 标题 "same 3/5, no constant"、
`evidence_index.py:98` 的 rung 文本 "with NO fitted constant"。

**证据**（`retry_controller.py`）：

| 常数 | 行 | 作用 |
| --- | --- | --- |
| `LIFT_PROOF_M = 0.03` | `:26` | **判定"抓住没抓住"的唯一阈值**（`:126` 的 `carried = lift > LIFT_PROOF_M`） |
| `FRAC` 默认 0.5 | `:25` | 抓取高度比例 |
| `STANDOFF = 0.11` | `:27` | 侧向退开距离 |
| `MODES` 默认 `top,side_x` | `:24` | 尝试顺序 |
| re-approach 4 次 + 5mm | `:136-143` | 释放校验 |

其中 0.03 这个数**不是新选的**：`solved/grasp_calibration.py:85` 已经用
`carried = bool(r["lift_above_control"] > 0.03)` 在 libero_object 任务 0 上定过一次。
也就是说，retry 轮里唯一决定"失败 → 重试"的那个阈值，是上一轮在**同一个套件**上标定出来的常数。
作者在 commit 正文里其实写对了（"the object rises by more than 3 cm"），
但 README 与 rung 文本把话说成了"没有任何拟合常数"。
准确说法应是："**接近方式的选择**不再依赖拟合阈值"，而这不是 README 写的字面意思。

> **什么会推翻我**：若 3cm 由测量自动导出（例如相对抬升分布的中位数），
> 或该常数在任何数据产生之前就已写入并登记为预注册。

---

### B6（major）留出套件被用来设计新版控制器，随后又被当作留出套件重报

**时间线**（git）：

1. `64e4f746` 阈值 0.140 在 5 个 libero_object 任务上选出，3/5；
2. `af2386f2` 在 libero_spatial 上冻结阈值，0/10；commit 正文写
   "The honest next step is therefore to use that feedback to switch approach on failure,
   rather than to fit another threshold"；
3. `8e1ba83b` 实现这个**由第 2 步结果决定**的控制器，然后**在同一个 libero_spatial 上**再跑，
   `closed_loop/README.md:28` 写作 "**libero_spatial（上轮的留出套件）** … 10 个任务全部失败"，
   并把 0/10 写进状态表 `:52` 的 "留出 | **0/10**"。

**为什么是问题**：留出集的作用是"设计完成后再检验"。这里设计**直接由该集的结果决定**，
第二次测量不再是留出检验。项目自己的规则也这么说：`docs/EXPERIMENT_PROTOCOL.md:64-68`
"Splits are disjoint and held-out is sealed … until it is, **no held-out result may be reported**"；
`docs/TASK_BENCHMARK.md:42-47` 同义。

**注意**：作者没有用这个 0/10 宣称泛化（`README:56-60` 明确"不宣称 3/5 是泛化成绩"），所以这不是数据造假；
问题是**同一套件被消费两次而报告没有标注**，读者会把第二行 0/10 当成独立留出证据。
结合 B2：这两次 0/10 其实是**同一个测量公式缺陷**的两次复现，不是两次独立的能力检验。

> **什么会推翻我**：存在第三套从未参与任何决策的套件上的结果；
> 或 README 明写"该套件已被用于设计，第二次测量不是留出检验"。

---

### B7（major）"OFFICIAL 任务完成"的分母：50 个官方 init 状态只用了第 0 个，n=1

**证据**：

- `.pruned_init` 是 torch zip 格式，`archive/data.pkl` 的 BUILD state 解出 `(1, (50, 110), dtype('f8'), ...)`
  → **50 个初始状态 × 110 维**（用 `pickletools.dis` 读操作码，未执行 pickle；
  文件 53039 字节 ≈ 50×110×8 + 开销，自洽）。
- 所有 runner 都用 `[0]`：`solved/adapter_control.py:56`、`holdout/runner.py:86`、`auto_runner.py:83`、
  `geom_runner.py:57`、`side_runner.py:82`、`retry_controller.py:50`、`run_one_task.py:43`、`transfer_runner.py:59`。
- LIBERO 官方协议不是单集布尔：`libero/lifelong/metric.py:112` 的 `init_states[indices]`（多状态）、
  `libero/configs/eval/default.yaml:5` 的 `n_eval: 20`、`metric.py:157` 的
  `success_rate = num_success / cfg.eval.n_eval`；`evaluate.py:244` 还开 20 个并行 env。
  → 官方单位是"20 个 episode 的成功率"，不是"1 个 episode 的 True"。
- `solved/README.md:11` 只写"官方结果 True（settle 100 步内持续为真）"，**没有写 n**；
  commit 4ee25e67 标题是 "COMPLETED an official external benchmark task"；
  `evidence_index.py:92` 的 rung 是 "OFFICIAL EXTERNAL TASK COMPLETED"。

**为什么是问题**：项目自己的协议 `docs/EXPERIMENT_PROTOCOL.md:70-73` 要求
"n=1 is exploration. Report n, the failure distribution, and no confidence interval on a single run"。
这里 n=1（1 个 init 状态 / 1 个 episode / 1 个任务），但产物既没写 n，也没写"50 个状态只取了第 0 个"。
"完成了一个官方任务"在 n=1 上不算错，但它与"官方基准"所暗示的量级差 20 倍 episode、50 倍 init 状态。

> **什么会推翻我**：README 里明写 "init_state[0], 1 episode, n=1（探索性）" 并把它与"完成官方基准任务"区分；
> 或提供 50 个 init 状态上的成功率。

---

### B8（major）"INDEPENDENTLY_VERIFIED" 名不副实；整条链没有独立验证

**证据**：

- `official/README.md:63`：`| 独立复核（verify.py 可脱离本会话重跑） | INDEPENDENTLY_VERIFIED |`。
- 仓库自己的定义：`docs/EVOBOT_VISION.md:65` `| Independently Verified | the independent evaluator passed it |`；
  `docs/EXPERIMENT_PROTOCOL.md:59-61` 给出同一串 rung。"verify.py 能重跑" ≠ "独立 evaluator 通过"。
- 9 个 verify.py **没有一个是独立 evaluator**：它们只读作者自己写的 JSON（§1.2）。
- `experiments/baselines/evidence_index.py:1-9` 注释宣称 "This script **DERIVES** that label by running every
  EvoBot acceptance verifier … so the status table cannot be written by hand to look better than the evidence"，
  但 rung 文本是**手写字典** `RUNGS`（`:36-99`）；脚本只派生 PASS/FAIL（`:125`）。
- 号称防 rung 通胀的 `benchmark/tests/test_evidence_discipline.py:60-70` 只读 `RUNGS` 字符串，
  且只对含 "Independently Verified"/"Generalization" 的条目检查是否**存在** `*verdict*.json` ——
  **完全不读 README**。LIBERO 那 9 条 rung 文本恰好都不含这两个词，因此这条测试对它们**零覆盖**。
- 可移植性：`official/verify.py:19` 把克隆路径硬编码为 `/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO`，
  换机器即失败；这不是"独立复核"，是"同机复核"。

> **什么会推翻我**：存在第三方/独立进程运行的记录；或 verify.py 会重跑 runner 并比对；
> 或 rung 表里 `INDEPENDENTLY_VERIFIED` 被改成 `SIM_TESTED` 并给出"独立"的所指。

---

### B9（major）side_grasp 的 verify.py 有一行永不失败的断言

```python
# setup/acceptance/evobot_libero_side_grasp_20261111/verify.py:30-31
for i in range(5):
    assert "episode terminated" in " ".join(side[i]["log"]) or True
```

`X or True` 恒为真。我把 5 个 `side_*.json` 的 `log` 全部替换成 `["no termination note here"]` 后，
verify.py **仍然 exit 0**。这一行对应 `side_grasp/README.md:34-38` 自曝的 harness bug ——
那次披露的唯一机器检查是空转的。

> **什么会推翻我**：把该行改成真断言（去掉 `or True`）后，清空日志的变异会让 verify.py 失败。

---

### B10（major）auto_approach 对 side_y 的"否证"没有任何检查

`auto_approach/verify.py:32-46` 把 `side_y_on_tall_bottles: "both still fail, 504 and 651 mm"`
写在**打印的 dict 字面量**里，全文没有一处 assert 读 `side_y_*.json`。实测：

- 删除 `side_y_2.json` / `side_y_4.json` → verify.py exit 0；
- 把两者改成 `official_success: true, release_xy_error_m: 0.0` → verify.py **仍然 exit 0**。

而 commit 64e4f746 与 `README.md:49` 把 side_y 作为"**三个变体都试过了**，所以剩下的失败不是参数没调对"的三证据之一。
clamped 那一路**有**断言（`:29-30`，我改成 5/5 后确实 exit 1），side_y 那一路没有任何断言。
两个样本（0.5045 / 0.65102）本身也只是探索性观察。

> **什么会推翻我**：verify.py 里出现对 side_y_*.json 的断言。

---

### m8（minor）"0/10 留出"的 10 个任务共用同一个物体

10 个 libero_spatial BDDL 的 `(:goal `) 子句**完全相同**：`(And (On akita_black_bowl_1 plate_1))`；
`(:objects `) 块逐字节相同（我算过 objects 块的 md5：10 个文件全是 `4e6141a1245f`）。
差别只在 `(:init `) 里碗的初始区域。这也解释了为什么 10 个任务的"测得高度"**恒为 0.168**。
所以"0/10"是 **1 个物体 × 10 个初始位姿**，不是"10 个不同物体"的泛化检验；
README 说"两个套件的物体几何分布不同（libero_object 是罐头/瓶/盒，libero_spatial 是碗/盘）"在套件层面没错，
但把它读成"10 个样本的形状多样性"会高估样本量。结合 B2，这 10 次失败是同一个公式缺陷的 10 次复现。

> **什么会推翻我**：10 个 BDDL 的 `(:objects `) 块其实不同（我已比对过 md5，全同）；
> 或 runtime 用的不是这些 BDDL。

---

### m1（minor）"对照臂"的证据链缺一环：只有 1 次对照，且对照行未存档

`solved/README.md:20-24` 把"加入对照臂"当成整轮最有价值的方法论。代码 `grasp_calibration.py:78` 确实跑了
1 次对照（descend 0.06，夹爪不闭合），`:84` 用 `lift_above_control = object_dz - baseline_dz` 减掉它。但：

- 对照的结果只 `print` 到 stdout（`:80`），**没有写进** `calibration.json`；
- `calibration.json` 里 5 行的 `lift_above_control` **全部严格等于 `object_dz - 0.0234`**
  （0.1371−0.0234=0.1137 ✓，0.1358−0.0234=0.1124 ✓，0.0234−0.0234=0 ✓，5/5 精确成立），
  也就是这一列是**一个常量减法**，不是逐高度的独立对照测量；
- README 说的"翻转符号之前，object_dz 在所有高度都是同一个 0.0234"那次扫描**完全没存档**，
  `calibration.json` 只有翻转后的 5 行（其中 2 行仍显示 0.0234）。

所以"对照臂"这个故事：代码上有，产物上只剩一个可推导的派生列。

> **会推翻我**：给出对照行的原始记录（`CONTROL (gripper open): {...}` 的输出），或翻转前那次扫描的存档。

---

### m2（minor）geometry README 混用了两个臂的数据

`geometry/README.md:36` 说 bbq_sauce "最终落在 `[-0.014, 0.232]`，距目标区域轴 3.6cm"。
这是 `top_3.json` 的 final；产生 2/5 的 `mid_3.json` 的 final 是 `[-0.061, 0.159, 0.055]`，
离 basket 约 0.12 m，与"3.6cm"差 3 倍多。`verify.py:44` 把这个 3.6cm 写进 verdict 但不校验。
不影响 2/5 这个数，影响"两种机制"叙事里的那个数字。

> **会推翻我**：mid_3 的 final 确实是 `[-0.014, 0.232]`。

---

### m3（minor）"1/3 → 2/5"是跨集合比较

`geometry/README.md:1,18` 与 commit 9998e225 标题都写 "transfer 1/3 → 2/5"。
transfer 轮只跑 0/1/2；geometry 轮跑 0..4（后两个任务是**在看到 3 任务结果之后**才加进评测集的）。
在相同的三个任务上其实是 **1/3 → 2/3**。README:18 括号里写了"上轮同批前三个是 1/3"，
所以这是**表述保守而非夸大**，但把两个不同分母并排放在标题里仍会误导。

> **会推翻我**：5 任务集在 3 任务结果之前就已登记/固定。

---

### m4（minor）`SIM_TESTED` 与本仓库自己的定义不一致

`docs/EVOBOT_VISION.md:64`：`| Simulation Tested | ran in Gazebo |`。
LIBERO 跑在 MuJoCo/robosuite，不是 Gazebo。`official/README.md:62`、`adapter/README.md:34`、
`solved/README.md:48` 等都标 `SIM_TESTED`。按字面这是误用；按宽松义成立。
列出来是因为它说明 rung 词表在本仓库**没有单一权威定义**，而 `evidence_index.py` 又把它们当字符串用。

> **会推翻我**：仓库里存在另一处定义把 Simulation Tested 定义成"任意仿真"。

---

### m5（minor）"封存 BLOCKED_GOOD" 在 LIBERO 目录里没有含义

7 个目录有 `seal.txt`，内容固定为 26 字节的 `=== seal ===` + `BLOCKED_GOOD`。
在其它批次里这是"留出答案权限被封、复验仍不可读"的状态标记；LIBERO 目录里**没有留出答案文件**，
所以它不表示任何东西。它不是哈希封条（无摘要、无签名），**没有任何 verify.py 读它**，`official/` 连它都没有。
commit 正文每轮都以 "seal BLOCKED_GOOD" 收尾，容易被读成"产物被封存"。

> **会推翻我**：存在脚本校验 seal.txt 与产物哈希的绑定关系。

---

### m6（minor）holdout 的 verify.py 把样本内 3/5 写死在 verdict 里

`holdout/verify.py:30` 的 `in_sample_object_suite: "3/5 (threshold chosen on these)"` ——
这个 3/5 不在本目录任何产物中，也不重算（它在 `auto_approach/` 目录里）。

> **会推翻我**：同目录存在 in-sample 的 3/5 产物或引用。

---

### m7（minor）closed_loop 的"失败层级"表有一行在设计上不可观测

`closed_loop/README.md:41-44` 的表里"选错接近方式"一行写：样本内 1 例、留出 **0 例**。
`retry_controller.py:172-177` 对每个任务**总是依次尝试 `MODES` 里的全部方式**，
所以"选错接近方式"这个类别在留出侧**结构上恒为 0**，不是测出来的 0。
样本内那个"1 例"也是事后归因（top 失败、side 成功）。把它排成表格会让人以为做过两种设计的对比。

> **会推翻我**：存在一个"先选择、失败即止"的对照运行，其留出计数可观测。

---

## 4. Q2：README 的数字与同目录 JSON 是否一致？

我把每个 README 的数字都从 JSON 重算一遍。**大多数是对的**——这一点要明确说：
side_grasp 的 5 行表、transfer 的 3 行表、auto_approach 的成功/误差列、holdout 的 0/10 与 119.4–480.0 mm、
closed_loop 的 obj 5 行与 spa 10 行，我都能从同目录 JSON 复现到最后一位。

不一致的只有下面几处：

| # | README 数字 | JSON 实际 | 差异 |
| --- | --- | --- | --- |
| N1 | `auto_approach/README.md:27` 测得高度 `0.132` | `auto_0.json:10` 的 `measured height 0.131` | 1 mm。README 用的是日志里 3 位小数 extent 字符串相减（0.081−(−0.051)），不是 `auto_note` 的实测值 |
| N2 | `README.md:29` 的 `0.186` | `auto_2.json:10` 的 `0.187` | 1 mm |
| N3 | `README.md:30` 的 `0.145` | `auto_3.json:10` 的 `0.144` | 1 mm；这也是超过阈值 0.140 的唯一关键样本，余量 4 mm 被写成 5 mm |
| N4 | `solved/README.md:30-31` 的 0.035 / 0.1068 | `result.json:10` 写的是 `basket_1_main at [0.015, 0.252, 0.107]` | 见 B4 |
| N5 | `solved/README.md:20` "object_dz 在**所有**高度都是同一个 0.0234" | `calibration.json` 5 行里只有 0.08/0.10 两行是 0.0234 | 指"翻转符号之前"那次扫描，未存档（m1） |
| N6 | `adapter/README.md:14` "approach reached, 19 steps, err 0.012" | `adapter/result.json` 只有 `approach reached`，无步数/误差 | 这两个数是从**另一轮** `solved/result.json:11` 借来的 |
| N7 | `geometry/README.md:36` bbq 的 `[-0.014, 0.232]` / 3.6 cm | 是 `top_3.json` 的 final；`mid_3.json` 是 `[-0.061, 0.159, 0.055]` | 见 m2 |

**另外要说明**：即使数字对得上，也不代表它测的是声称的东西——B2 就是最好例子：
"测得高度 0.168" 在 JSON 里确实存在、可复算，但它是包围球直径，不是高度。

> **什么会推翻我**：对 N1/N2/N3，若 JSON 里存在 4 位小数的 `measured_height` 字段且与 README 相符；
> 对 N7，若 mid_3 的 final 确实是 `[-0.014, 0.232]`。

---

## 5. Q3：是否在后来称作"留出"的数据上调过东西？

| 提交 | 时间 | 做了什么 | 用了哪些数据 | 之后被叫什么 |
| --- | --- | --- | --- | --- |
| 73756061 | 11:32 | official，no-op 策略 | 无 | OFFICIAL，n=1 |
| a9440d82 | 11:39 | adapter，grasp 失败；reach_probe | 任务 0 | 负面 |
| 4ee25e67 | 11:53 | grasp_calibration（1 次对照），翻转夹爪符号，改瞄 contain region | 任务 0 | 完成 |
| 89e67d0c | 12:01 | BDDL 解析 + 3 任务 | 0,1,2 | 1/3 |
| 9998e225 | 12:15 | 几何推断抓取；mid/top(0.85)；(README 声称还有 0.70) | 0..4 | 2/5 |
| d60b5d7c | 12:53 | side_x + 释放校验 | 0..4 | 并集 3/5 |
| 64e4f746 | 13:11 | **阈值 0.140 在 5 个样本上选出** | 0..4 | 3/5（自认拟合） |
| af2386f2 | 13:44 | libero_spatial 冻结阈值 → 0/10；**看到失败后扩展解析器** | spatial 0..9 | 留出失败 |
| 8e1ba83b | 14:12 | 用 lift 反馈替换阈值（设计源自上一步） | object 0..4 + spatial 0..9 | 3/5 + 0/10 |

**结论**：

1. **阈值 0.140 在 5 个样本上拟合** —— 作者自己披露了三次（`auto/README.md:66`、commit、`holdout/README.md:5-6`）。**披露准确。**
2. **af2386f2 的"看到留出数据后改解析器"披露准确**：我 diff 了 `auto_runner.py`（样本内）与 `holdout/runner.py`，
   差异**只有**两部分：(a) `parse_goal` 增加 `keep or pairs` 回退；(b) 新增 `goal_mode == "object"` 分支，
   目标取 `pos_body(rif) + [0, 0, 0.03]`。被检验的阈值 `AUTO_HEIGHT_M` 与选择规则**一字未动**。
   README:29-36 与 commit 都写了这件事，连"引入新的未验证成分"都写了。**披露准确。**
3. **披露不完整的三处**：
   a. 第一次留出重跑"直接 0 结果"**没有任何产物**，所以"0/10"是**改了解析器之后**的第二次运行；
   b. `+ [0, 0, 0.03]` 是**看过留出套件 BDDL 之后新加的常数**，并立刻用在留出测量里（README 没说它是新定的）；
   c. 留出套件在 8e1ba83b 被第二次使用（B6）。
4. **但最大的问题不是"在留出数据上调参"，而是 B1/B2**：9998e225 那一轮"试了 0.70/0.85"这件事本身没发生；
   而 0/10 的机制是几何测量公式缺陷。也就是说，"用数据选参数 → 留出打脸 → 用反馈替代"这条叙事链上，
   至少有两环的证据不支持叙事。

> **什么会推翻我**：给出第一次留出运行的产物；或证明 `+0.03` 在 af2386f2 之前就存在于某个 runner 里；
> 或证明 B1/B2 的代码事实不成立。

---

## 6. Q5：是否有"把脚本常数说成能力"？是否有 ≤5 样本的能力主张？

| 主张 | 样本 | 是否自认样本小 | 我的判断 |
| --- | --- | --- | --- |
| solved "官方任务完成" | 1 任务 / 1 init 状态 / 1 episode | **否**（未写 n） | B7：口径过宽 |
| transfer 1/3 | 3 | 是（README:17） | 披露充分 |
| geometry 2/5 | 5 | 是（README:56） | 披露充分，但机制结论见 B1/m2 |
| side 并集 3/5 | 5 | 是（README:52 "并集不是系统的成绩"） | 本项目里做得最好的一处诚实披露 |
| auto 3/5 | 5 | 是（README:66 "属于拟合"） | 披露充分 |
| 释放误差失败检测器 | 5（2 成功 + 3 失败） | 否 | **B3：被同批 60/98 mm 反例否定，且被下游两轮当作既定规则** |
| "摘要在物体、不在我"（几何抓取） | 5 | 是 | **B2：它算的是包围球半径，不是物体几何** |
| "no fitted constant"（retry） | 5 | 是 | **B5：常数仍在** |
| "两种方式都抓不住碗" | 10 任务 × 2 尝试 | 部分 | 不是"抓不住"，是**没碰到**（B2）；且 10 个任务同一物体（m8） |

**"把常数说成能力"最典型的一处**：retry 轮的"闭环"能力。核心判据是 `lift > 0.03`；
这个常数不是测出来的，是上一轮在同一套件上定的（B5）。README:25 的措辞是"没有拟合常数"。

**另一处**：geometry 轮标题的 "the number comes from the object, not me"。
实际 `gz = geom 中心 + (FRAC−0.5)×2rbound`，在 FRAC=0.5 时就是**几何体中心的 z**，
是一个固定姿势下的常量，不随物体形状/位姿变化。说"数字来自物体"形式上对，
但它不是 README 说的那个量（z 范围），也就不能支撑"几何决定抓取"这个因果。

---

## 7. Q6：是否有 rung 主张缺乏产物支持？

| 位置 | 主张 | 支撑情况 |
| --- | --- | --- |
| `official/README.md:63` | `INDEPENDENTLY_VERIFIED` | **不支持**，见 B8 |
| `official:61-62` / `adapter:33-34` / `solved:46-48` | `IMPLEMENTED` / `SIM_TESTED` | 代码在、产物在；但 `SIM_TESTED` 与仓库自己的 "ran in Gazebo" 定义不符（m4） |
| `transfer:46` | "目标解析 IMPLEMENTED + SIM_TESTED（3/3）" | 支持（t0–t2 的 `parsed_*` 字段） |
| `geometry:45` | "几何推导抓取 IMPLEMENTED + SIM_TESTED" | 代码在；但"几何"是包围球（B2），且"试了三个比例"未发生（B1） |
| `side:44-45` | "侧向接近 / 释放前校验 IMPLEMENTED + SIM_TESTED（同时是失败检测器）" | 前两项支持；"失败检测器"见 B3 |
| `auto:57` | "按几何选接近方式 IMPLEMENTED + SIM_TESTED" | 选择逻辑真实存在（我复算 5/5 一致）；但输入量是被放大的假高度（B2） |
| `closed_loop:50-52` | "闭环重试 IMPLEMENTED + SIM_TESTED / 无拟合常数" | 重试真实触发（obj_3 两次尝试）；"无拟合常数"见 B5 |
| `holdout` 全篇 | 0/10 留出 | 数字支持；"留出"资格见 B6，机制解释见 B2 |
| `evidence_index.py:90-98` rung 文本 | 由 `evidence_index.py` "DERIVED" | **不支持**：rung 是手写字典，派生的只有 verify.py 退出码（B8） |

---

## 8. 我无法检查的部分（以及为什么）

1. **任何一次运行是否真的发生过** —— 要求不跑仿真。所有 runner 都是"读 sim 状态 → 驱动 → 写 JSON"，
   JSON 可以手写；`stepped: 999` 的变异能过 verify.py 就证明这一点。没有日志、时间戳、种子、run id、
   命令行或环境变量记录。
2. **"第一次留出重跑 0 结果"**（af2386f2 披露）—— 没有产物。
3. **"第一版 side grasp 崩溃、3 个任务无结果"**（d60b5d7c 披露）—— 没有产物，且对应断言是空转的（B9）。
4. **翻转夹爪符号之前那次"所有高度都是 0.0234"的扫描** —— 未存档（m1）。
5. **`region_probe.py` 的输出（0.035 / 0.1068）** —— 未存档（B4）。
6. **每次配置跑了几次、是不是取了最好的一次** —— 产物里没有重复运行记录。
   如果做过"跑 3 次留 1 次最好"，现有证据无法发现。对所有 9 个目录都成立，我无法排除。
7. **`0.70` 那一组** —— 不存在任何文件，只能确认"没有"，无法确认"跑过"。
8. **LIBERO 官方评估本身** —— 我没有跑 `libero/lifelong/evaluate.py`，也没有参考策略的对照分数，
   无法判断 3/5 在 libero_object 上算好还是差（不是我的任务）。
9. **B2 的物理解释**：我只能从"资产 XML 的碰撞盒"与"抓取 target"两点算出上表间隙。
   我没有在仿真里确认夹爪在该高度闭合时确实什么也没夹到——但 `carried=False / lift=0.000` 与之一致。
   若该资产的碰撞几何在运行时被缩放或替换（我没有证据），B2 的数值需要重算，
   但"测量量 = geom 中心 ± rbound 的球投影"这个代码事实不受影响。

---

## 9. 附：如何复现我的检查

```bash
cd /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_redteam_20261111
python3 falsify_harness.py        # 36 个变异用例：复制目录 → 篡改 JSON/日志 → 跑 verify.py → 记退出码
```

我的所有写操作都限制在本目录（`REVIEW.md`、`FALSIFICATION.log`、`falsify_harness.py`），
临时副本 `_falsify/` 与中间脚本已删除；仓库其它位置一个字节未改
（`git status --porcelain` 只显示本目录与队友的 `evobot_tall_bottles_20261111` 两个未跟踪目录）。

---

## 10. 一句话总结

**转录层是干净的（9 个 verifier 大多真能失败、多数数字可复算），但实验层有两处根本缺陷：
"三个抓取比例结果相同"这个否证所依赖的比例变量根本没有进入控制器，且那批 JSON 与落盘脚本的日志格式不一致、
不可能是它产生的（B1）；"几何推导抓取"算的是包围球半径而非几何 z 范围，在留出套件上抓取点悬在碗顶上方
4.8–13.9 cm——这才是 0/10 的机制，而报告把它归因为"形状差异/抓取能力缺失"（B2）。
再叠加"无拟合常数"与代码矛盾（B5）、留出集被二次消费（B6）、官方口径缺分母（B7）、
"独立验证"没有独立方（B8），以及两条永不失败/未接线的 verifier 断言（B9/B10）。
这些不是文风问题：B1/B2 是后续三轮设计的前提，B5 是最后一轮的标题。**

**如果只能修一件事**：先修 `geom_runner / auto_runner / runner / retry_controller` 里那四处同一段
"`geom_xpos ± geom_rbound`" 的高度估计，然后用真实的 init_state 重新跑一遍——因为它同时决定了
"几何抓取"、"高度阈值"、"留出 0/10"和"闭环重试"四条结论的真假。
