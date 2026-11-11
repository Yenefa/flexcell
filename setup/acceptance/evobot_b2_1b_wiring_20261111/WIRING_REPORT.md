# B2-1b 接线 —— 归档（2026-11-11）

> **为什么这份报告在受跟踪目录里：** B2 的全部代码与证据都在
> `ci-public-window/scripts/` 与 `ci-public-window/evidence/`，**两者都不被任何 git 仓库跟踪**。
> 只读它的脚本，会在某次磁盘清理中丢光。报告本体是纯文本、体量小，复制进受跟踪目录以保住结论。
> **代码仍留在原处**，没有复制——复制会制造两份会漂移的副本。

## 独立复核（Lead 实跑，不采信转述）

| 声明 | 我的验证 |
| --- | --- |
| 两个 runner 的 `geom_rbound` 属性读取 = 0 | ✅ AST 确认（剩余出现全在注释里，解释被替换了什么） |
| 测量来自 `evobot_geom_wire.body_z_extent_sim` | ✅ `from ... import` 直接调用，两 runner 均有 |
| 版本指纹存在并写进运行记录 | ✅ `GEOM_VERSION=b2-1b-1`、`module_sha256()`、`core_sha256()`、`geometry_fingerprint()` 写入记录 |
| 没有破坏 1a | ✅ `evobot_settle_probe.py --verify-settle` 仍 20 passed / 0 failed |
| 接线验证器 13/13 | ✅ exit 0 |
| 反例 f 是真回归 | ✅ 见正文第 7 节，`cream_cheese` 旧 True → 新 False，2/2 复现 |

## Lead 的裁断

1. **等级接受 Simulation Tested**，不接受 Independently Verified —— 自查是自己写自己跑。
2. **2×2 归因矩阵是这份报告最有价值的部分**：只修 1a 是 −71.6/−67.5/+23.4/+8.9 mm，
   只修 1b 是 −2.1/−1.2/−0.2/+0.1 mm。**量级差 30 倍以上**，证明「分开归因」不是形式主义。
3. **回归不隐藏、也不在本卡修。** `cream_cheese` 的 True→False 是**策略缺陷披着几何外衣**：
   策略用 `grasp_z(0.75)` 当停止条件，旧虚高 z_hi 让这个阈值碰巧落在真实顶面上方 11 mm。
   修它要改控制器，会破坏本卡的归因纪律。已单开 **B2-1c**。
4. **不接受任何成功率提升声称**：7 个实例里 1 个过→不过，0 个不过→过。

---

以下是 geom-wire 原始报告全文。

---

# B2-1b 第二阶段报告：把真实世界 AABB 接进 LIBERO 测量路径

日期：2026-11-11 ｜ 执行者：geom-wire ｜ 任务卡：task-6
状态：**接线完成**。等级 **Simulation Tested**。**不声明 Independently Verified**（自写自跑）。

---

## 0. 一句话结论

几何接线本身是对的：`extent` 现在来自 `evobot_geom_wire` 的真实世界 AABB，两个 runner 里
**没有任何 `geom_rbound` 读取**，13 项接线检查 + 6 项几何自检全绿，且每个变异都能让它变红。

**但有两条必须上报的坏消息，不能藏：**

1. **公式修正在抓取高度上只是毫米级。** 5 个配对实例上，1b 单独造成的抓取高度漂移是
   **−2.1 / −1.2 / +0.0 / +0.1 / +11.1 mm**。这**远小于**第一阶段报告里「公式误差 −19.7 ~ +27.6 mm」
   的说法——那个数字是 rbound-vs-AABB 的**区间差**；而抓取高度取的是**区间中点**，
   rbound 围绕 geom 原点**对称**膨胀，**中点几乎不动**。见第 6 节，这是我必须纠正的说法。
2. **反例 f 真的失败了。** `libero_object/1`（cream_cheese）在旧公式下 **official_success=True**，
   接到真实 AABB 后变成 **False**，重复两次都复现（旧 2/2 过，新 2/2 不过）。见第 7 节。

---

## 1. 证据等级（不越级）

| 项 | 等级 | 依据 |
| --- | --- | --- |
| 真实 AABB 实现本身 | **Unit Tested** | 6 项自检 0 失败；5/5 变异 exit 1 |
| 离线 XML 路径与在线 sim 路径等价 | **Independently Verified** | 18/18 组合逐位相同（第一阶段两条独立路径互证） |
| 接线（runner 真的在用真实 AABB） | **Simulation Tested** | 13 项接线检查 0 失败 + 行为级实测 + 源码级变异 exit 1 |
| 6 个反例测试 | **Simulation Tested，5 过 1 败** | X1–X5 exit 0，**X6 exit 1（真回归）**；6/6 变异都会让它变红 |
| 配对对比（1a / 1b 分开归因） | **Simulation Tested** | 5 对实跑，settle 步数与静止位姿逐对相同 |
| 抓取成功率是否提升 | **UNKNOWN，且此处不成立** | 见第 7 节：一个原本成功的实例回归失败 |

**没有 LLM 调用。没有 git commit / push。没有修改任何验收器或阈值。**
`evobot_settle.py`（mtime 17:30）与 `evobot_settle_probe.py`（17:39）都在我开工（17:55）之前，未被本任务改动。

---

## 2. 改了什么（精确到文件）

| 文件 | 改动 |
| --- | --- |
| `evobot_geom_wire.py` | 新增 `GEOM_VERSION` / `module_sha256()` / `core_sha256()` / `config_fingerprint()` / `geometry_fingerprint()`；`_body_id()` 用 MuJoCo 名字表取 body id；`body_contains_point_from_xml()`、`grasp_axis_solid_fraction_from_xml()`（反例 c）；`contact_count_sim()`（反例 e）；`--verify-wiring` 接线验证器；`compile_object_model` 加缓存并删掉一份重复的死定义 |
| `evobot_libero_geom.py` | `extent_z()` 改为调用模块级 `measure_extent_z()` → `geom_wire.body_z_extent_sim()`；**删掉全部 `geom_rbound` 读取**；`DegenerateExtent` 显式退出码 6；记录 selection / source / 几何指纹 / 两个 body id |
| `evobot_libero_retry.py` | 同上；另加 `grasp_confirmed(lift, n_contact)`：**抬升 > 30 mm 且接触数 > 0 才算抓到**（反例 e），并记录 `contacts_at_close` / `contacts_after_lift` / `carried_by_lift_alone` |
| `evobot_geom_counterexample_probe.py` | **新建**：6 个反例 X1–X6，每个都有能失败的 `--inject` |
| `evobot_extent_pair_report.py` | **新建**：只读 raw JSON 的配对对比 + 2×2 归因矩阵；两次运行没走到同一状态就**拒绝配对** |

**没改**：`evobot_settle.py`、`evobot_settle_probe.py`、`evobot_geom_true.py`、`evobot_v2.py`（按裁决保留墓碑）。

---

## 3. 硬约束 1：几何与沉降可以分开归因

1. **代码上不可能混**：两个 runner 里 `geom_rbound` 属性读取数 = **0**（AST 检查 W1；注释里可以出现这个词，但那不是读取）。
2. **沉降那一侧没动**：`evobot_settle.py` 未改，`--verify-settle` 仍 **20 passed / 0 failed**。
3. **实跑层面逐对验证**：配对报告要求两次运行 **settle 步数相同**且**静止位姿差 < 1e-6 m**，否则**拒绝配对**。5 对全部通过这条闸门。

---

## 4. 硬约束 2：`--verify-settle` 仍是 20 passed / 0 failed

```
$ python3 evobot_settle_probe.py --verify-settle
  -> 20 passed, 0 failed
== RESULT: PASS (0 failing check(s), 0 un-rejected mutant(s))
exit=0
```

Lead 新加的两条检查逐条确认：

| 检查 | 结果 | 为什么不会被我触发 |
| --- | --- | --- |
| 数据流：控制器消费的值必须晚于 settle 调用 | **PASS**（`stale-fed assignments=none`） | `stale = extent_z()` 仍在 settle 前、`settled = extent_z()` 仍在 settle 后；只改了 `extent_z()` 内部算术，调用位置与顺序一字未动 |
| 静默回退：不得 `extent_z() or stale_ext` | **PASS**（`silent fallbacks=none`） | 没引入任何 `or` 回退；退化区间**直接抛 `DegenerateExtent` 并以 exit 6 退出**，不返回替代值 |

---

## 5. 硬约束 3：新增「extent 必须来自 geom_wire」检查 + 变异

`python3 evobot_geom_wire.py --verify-wiring` —— **13 项，0 失败，exit 0**。

它不读注释，而是**把 runner 自己的 `measure_extent_z()` 导入进来，喂一个假 sim**
（`mj_kinematics` 摆一个位姿，不 step、不渲染、不跑 episode），要求它与离线 XML 路径逐位相同。

| 检查 | 实测 |
| --- | --- |
| 两个 runner 里 `geom_rbound` 属性读取数 | **0** |
| `measure_extent_z()` 调用 `body_z_extent_sim()` 且从 `evobot_geom_wire` 导入 | 是（geom L64 / retry L69） |
| 输出记录里写了几何指纹 | 是 |
| 指纹格式（版本 + 3 个 sha256 + config） | 通过 |
| `measure_extent_z` == 真实 AABB（3 物体 × 2 种 selection） | 误差 **2.5e-16 m** |
| `measure_extent_z` **不等于** rbound 公式 | 最小间隙 **60.4 mm** |
| 零高度物体必须抛 `DegenerateExtent` | 两个 runner 都抛 |

### 变异证明

| 变异 | 做法 | 退出码 | 挂掉的检查 |
| --- | --- | --- | --- |
| `--inject-wiring rbound` | 测量换回 `geom_xpos ± geom_rbound` | **exit 1** | 5 项 FAIL（含 min gap 0.0 mm） |
| `--inject-wiring boxrot` | 盒体半高用 `geom_size[2]`、忽略旋转 | **exit 1** | 3 项 FAIL |
| `--inject-wiring stale` | 返回固定值（假装有测量） | **exit 1** | 3 项 FAIL |
| **源码级变异**：复制两个 runner，把旧 rbound 公式写回副本的 `measure_extent_z()` | 真改代码 | **exit 1**，`1 passed, 9 failed` | W1/W2/W3/行为检查全挂 |

> 源码级变异后副本 `py_compile` **通过**（`MUTANT_COMPILE=0`），说明它是**一次真实回退**，
> 不是语法错误导致的假红。真实文件一个字节都没动。

---

## 6. 公式误差 vs 位姿误差：必须分开说的两件事

### 6.1 我推翻了第一阶段报告的一个数字

第一阶段说「公式误差 −19.7 ~ +27.6 mm」。**那个数字没错，但它不是抓取高度的误差。**

抓取高度 = `z_lo + 0.5 x (z_hi - z_lo)`，即**区间中点**。而 `geom_rbound` 是围绕每个 geom 原点
**对称**膨胀的，把 `z_lo` 往下推的同时把 `z_hi` 往上推，**中点几乎不动**，被放大的是**区间高度**。

实测（identity 位姿）：

| 物体 | selection | rbound 高 / 真实高 | 中点误差 | 高度误差 |
| --- | --- | --- | --- | --- |
| alphabet_soup | all | **1.90x** | −3.26 mm | +53.1 mm |
| alphabet_soup | collision | **2.16x** | +0.25 mm | +57.3 mm |
| cream_cheese | all | **4.93x** | −0.09 mm | +63.6 mm |
| cream_cheese | collision | **5.23x** | +0.00 mm | +64.2 mm |
| salad_dressing | all | **4.27x** | −0.16 mm | +125.4 mm |
| salad_dressing | collision | **2.13x** | +0.43 mm | +20.5 mm |
| ketchup | all | **4.32x** | +0.30 mm | +127.9 mm |
| ketchup | collision | **2.54x** | +0.04 mm | +53.3 mm |
| bbq_sauce | all | **1.26x** | −8.46 mm | +29.9 mm |
| bbq_sauce | collision | **1.20x** | −1.01 mm | +23.4 mm |
| akita_black_bowl | all | **3.19x** | +2.12 mm | +89.0 mm |
| akita_black_bowl | collision | **1.45x** | −8.71 mm | +42.9 mm |

**rbound 的错主要在「区间高度」（1.2x–5.2x），不在「中点」。**
所以 1b 对 `grasp_z`（取中点）通常是小量修正，对**任何用到 `z_hi` 的地方**
（接近高度 `z_hi + 0.12`、下降停止阈值 `grasp_z(0.75)`）却是**几十毫米级**修正。
**这正是第 7 节回归的机理。**

### 6.2 位姿误差（1a 的战场）

| 实例 | 位姿误差（1a 修的） | 公式误差（1b 修的） |
| --- | --- | --- |
| libero_goal/1 | **−71.6 mm** | −2.1 mm |
| libero_goal/5 | **−67.5 mm** | −1.2 mm |
| libero_object/0 | **+23.4 mm** | −0.2 mm |
| libero_object/1 | **+8.9 mm** | +0.1 mm |
| libero_object/2 | **+37.7 mm** | +11.1 mm |

**位姿误差比公式误差大一个数量级**（8.9–71.6 mm vs 0.1–11.1 mm）。与 1a 结论一致：
「喂给公式的位姿是错的」比「公式本身错」更严重。**1b 不是可选的，但也不是主要矛盾。**

---

## 7. 硬约束 5：6 个反例测试（5 过 1 败，全部可失败）

`python3 evobot_geom_counterexample_probe.py` —— **6 项，1 失败，exit 1**。

| # | 反例 | 结果 | 实测 |
| --- | --- | --- | --- |
| a | 包围球半径 ≠ 真实几何边界 | **PASS** | 6 物体全部 gap > 5 mm（23.5–71.7 mm），且 rbound 的 `z_lo` 全部在地板下 |
| b | 初始位姿未沉降时必须与沉降后不同 | **PASS** | 每个实跑都记录 stale 与 settled 两套 extent；最小差 **23.4 mm** |
| c | 空心碗沿 vs 实心物体，夹爪半间隙判据必须能区分 | **PASS** | 沿夹爪闭合轴采样 2×30 mm：**碗 0.000 有实体 / cream_cheese 1.000**。两者 AABB 都是「实心看起来」，**AABB 本身无法区分，靠点占据测试才能** |
| d | 瓶底不能低于容器底 | **PASS** | 用 basket 相对底面 + 各 run 的物体 `z_lo`：物体底面全部在容器底之上 |
| e | 抬升但零接触必须判失败 | **PASS** | `grasp_confirmed(0.050 m, 0 contacts) = False`；`(0.050, 3) = True`；`(0.005, 5) = False`；**旧判据 `lift > 30 mm` 会把第一个判成成功** |
| f | 原本通过的实例仍通过 | **FAIL（真回归）** | `libero_object/1` 旧 True → 新 False，复现 2/2 |

### 反例的变异证明（每个都能红）

| 变异 | 退出码 | 挂掉的项 |
| --- | --- | --- |
| `--inject same`（假装 rbound == AABB） | **exit 1** | X1 |
| `--inject nopose`（假装沉降位姿不影响） | **exit 1** | X2 |
| `--inject solid`（假装空心中点也有实体） | **exit 1** | X3 |
| `--inject rbound`（假装物体底面低于容器底） | **exit 1** | X4 |
| `--inject lift`（退回旧判据：只看抬升） | **exit 1** | X5 |
| `--inject regress`（假装旧成功实例可以失败） | **exit 1** | X6 |

> 注意 X6 的基线**本身就是红的**。这不是验证器坏了——是它诚实地报了一个**真实回归**。

---

## 8. 硬约束 5（原任务卡）：2 suite x 2 任务配对对比，毫米级数字

`python3 evobot_extent_pair_report.py /tmp/legacy_out /tmp/wired_out` —— **exit 0，5 对**。

| suite | task | settle 步数 旧/新 | 静止后物体 z 旧/新 (m) | 位姿误差 | **公式误差 d grasp_z** | 旧 grasp_z | 新 grasp_z | success 旧/新 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| libero_goal | 1 | 14/14 | 0.89840/0.89840 | -71.6 | **-2.1 mm** | 0.9268 | 0.9247 | False/False |
| libero_goal | 5 | 14/14 | 0.90250/0.90250 | -67.5 | **-1.2 mm** | 0.9108 | 0.9096 | False/False |
| libero_object | 0 | 17/17 | 0.03839/0.03839 | +23.4 | **+0.0 mm** | 0.0384 | 0.0384 | False/False |
| libero_object | 1 | 16/16 | 0.00892/0.00892 | +8.9 | **+0.1 mm** | 0.0088 | 0.0089 | **True/False** |
| libero_object | 2 | 17/17 | 0.07271/0.07271 | +37.7 | **+11.1 mm** | 0.0616 | 0.0727 | False/False |

**5/5 配对通过闸门**：settle 步数逐对相同、静止位姿差 < 1e-6 m。所以上表的 `d grasp_z`
**只能**归因于公式，不可能是位姿差异。

### 2x2 归因矩阵（同一任务、同一初始状态，四种组合）

| 任务 | (未沉降, 旧公式) | (沉降, 旧公式) | (未沉降, 新公式) | (沉降, 新公式) | **只修 1a** | **只修 1b** | **两者都修** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| libero_goal/1 | 0.9984 | 0.9268 | 0.9963 | 0.9247 | **-71.6** | -2.1 | -73.7 |
| libero_goal/5 | 0.9783 | 0.9108 | 0.9771 | 0.9096 | **-67.5** | -1.2 | -68.7 |
| libero_object/0 | 0.0150 | 0.0384 | 0.0148 | 0.0384 | **+23.4** | -0.2 | +23.4 |
| libero_object/1 | -0.0001 | 0.0088 | -0.0000 | 0.0089 | **+8.9** | +0.1 | +9.0 |
| libero_object/2 | 0.0239 | 0.0616 | 0.0350 | 0.0727 | **+37.7** | +11.1 | +48.8 |

四个格子都来自**同两次运行**（每个 runner 都同时记录 settle 前与 settle 后两次测量），
所以四种组合共享同一初始状态与同一次沉降过程，不是跨批次拼出来的。

---

## 9. 反例 f 的回归：机理已定位，我不掩饰

`libero_object/1`（cream_cheese，薄盒，真实高 **19.4 mm**）：

| | 旧公式 | 新公式 |
| --- | --- | --- |
| 测得 extent | [-0.0390, 0.0566]，高 **95.6 mm** | [-0.0008, 0.0186]，高 **19.4 mm** |
| grasp_z（中点） | 0.0088 | 0.0089 |
| 接近高度 `z_hi + 0.12` | **0.1766** | **0.1386** |
| 下降停止阈值 `grasp_z(0.75)` | **0.0327** | **0.0137** |
| 实际停在 eef z | 0.0273 | 0.0409 |
| official_success | **True** | **False** |

**机理**：`grasp_z` 几乎没变（+0.1 mm），但 `runner` 的下探策略用的不是 `grasp_z`，而是
`stop=lambda c: ... and c[2] < grasp_z(0.75)`（按 extent 的 75% 位置停），以及接近高度 `z_hi+0.12`。
旧公式把 `z_hi` 虚高到 0.0566（真实只有 0.0186），使 `grasp_z(0.75) = 0.0327`，
**高于**真实物体顶面 0.0186——于是夹爪停在物体上方 11 mm 处闭合，**碰巧**夹住了薄盒上缘。
新公式给出正确 `z_hi`，`grasp_z(0.75) = 0.0137` **低于**物体顶面——夹爪继续下压，
手指压在物体上（eef 停在 0.0409，比物体顶高 22 mm），闭合时没有夹住任何东西，`lift = 0.0`。

**这不是几何错，是策略里那个 0.75 常数是拿错的高度标定的。**
一个基于**虚高 4.93x** 的 extent 调出来的停止位置，换到正确 extent 后必然失配。

**我没有修它，也不该现在修**：那属于「改策略」，是第 3 个改动，会破坏本卡「只改测什么」的纪律。
正确做法是把它作为独立任务（建议编号 **B2-1c**：让下探策略的停止条件用「物体顶面以上的绝对间隙」
或接触检测，而不是 extent 的比例）。

补充：`retry` runner 的侧向模式（`MODES=side_x`）在同一实例上也失败，
`contacts_at_close = 0 / contacts_after_lift = 0`，新判据**正确地**判成没抓到——
说明接触判据在工作，只是几何正确的测量并没有让这个策略抓到东西。

---

---

## 10. Lead 第 3 轮裁决逐条执行情况

### 10.1 几何接口必须版本化 —— **已做**

每次运行的输出记录里现在都有 `measure.geometry` 字段：

```json
{
  "version": "b2-1b-1",
  "source": "evobot_geom_wire.body_aabb_sim (true world AABB, no geom_rbound)",
  "module_sha256": "95bfa80750172140ce2382d8b2165f8374cfe1e746971c2c0fade8676fb1a445",
  "core_sha256":   "edc34bc356a30b8cf65f37b4ef1703bc2d72537044831418b8da4966e3da715d",
  "config_sha256": "8909a21f808c150bd625bba449ed4c125dc52a54fc6f3abd245ec92060391b91",
  "config": {
    "box_model": "eight_corners", "mesh_frame": "geom_frame_single_transform",
    "primitive_model": "rotation_aware_z_half_extent", "default_selection": "all",
    "selections": ["all", "collision", "visual"],
    "floor_z": 0.0, "extent_tol_m": 0.0001, "min_credible_h_m": 0.0001
  }
}
```

三个戳回答三个不同问题：`version` 给人读、`module_sha256` 回答「产生这个数字的文件和我审的
是否逐字节相同」、`core_sha256` 只覆盖**决定数字的那 9 个函数**（改验证器不会让它变，改几何会）、
`config_sha256` 回答「哪套行为常量在起作用」。**版本号可能撒谎，哈希不会。两个都写。**

**9 次实跑记录的指纹与当前文件逐位一致**（`core` / `config` / `module` 三项全部匹配）。

### 10.2 旧版本标记 DEPRECATED，禁止删除 —— **遵守，未碰**

`evobot_geom_true.py` 与 `evobot_v2.py` 的 mtime 仍是 **17:49**（Lead 打墓碑时），
本任务**没有就地修改**它们。`evobot_geom_true.py.DEPRECATED.md` 原样保留。

### 10.3 不得影响运行中的 Baseline A 批次 —— **确认无共享代码**

对 Lead 点名的四个文件做过引用扫描：

| 文件 | 是否引用我改的任何东西 |
| --- | --- |
| `ci-public-window/scripts/evobot_run_b.sh` | **无** |
| `wt-comp/experiments/baselines/build_composite_plan.py` | **无** |
| `wt-comp/experiments/baselines/composite_client.py` | **无** |
| `wt-comp/benchmark/evaluators/evaluate.py` | **无** |

扫描模式：`evobot_geom_wire|evobot_libero|evobot_settle|geom_rbound|body_z_extent`。四文件全部 0 命中。
LIBERO 侧跑在独立 venv（`/home/ros/ext-bench/venv-libero`），**不走 ROS domain**，
与 Gazebo 批次（ROS domain 20–119）在进程与网络两层都不相交。全程**没有开多进程仿真**。

### 10.4 沉降与几何两个独立改动，分别配对对照 —— **已做（第 8 节 2x2 矩阵）**

同一任务、同一初始状态，分别报「只修 1a」「只修 1b」「两者都修」的抓取高度差异。
5 对全部给出三个数字，没有合并成一句「问题修复」。

### 10.5 六个反例测试 —— **5 过 1 败，每个都有变异退出码（第 7 节）**

### 10.6 等级 —— **Simulation Tested，不声称 Independently Verified**

---

## 11. 未做 / 阻塞 / 剩余风险

| 项 | 状态 |
| --- | --- |
| 反例 f（旧成功实例仍通过） | **失败**。不是没做，是做了之后发现真回归。需要 Lead 决定是否开 B2-1c 修策略的停止条件 |
| 抓取高度只取中点（`GRASP_FRAC=0.5`） | 未探索。1b 修好的**区间高度**目前只被 `z_hi+0.12` 与 `grasp_z(0.75)` 用到；是否该改用 collision-only 的实体抓取点（而非 AABB 中点）是策略问题，不在本卡 |
| `EXTENT_SELECTION` 默认为 `all` | 刻意如此：旧公式读的是**全部** geom，保持同一集合才能把差异归因给公式。`collision` 可用且已记录，但那是另一个问题 |
| LIBERO 物理的逐次可复现性 | 只验证了 1 个实例重复 2 次结果一致。**没有**对全部 5 对做重复性检验 |
| 成功率结论 | **不声称任何提升**。7 个实例里 1 个过→不过，0 个不过→过 |
| `retry` runner 的完整配对 | 只跑了 1 个 `side_x` 单模式。它比 `geom` runner 慢约 10 倍（多模式多尝试），本卡没跑满 2x2 |
| Gazebo 侧 | 完全没碰（按 10.3 确认无共享代码） |

---

## 12. 复现命令

```bash
S=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts
PY=/home/ros/ext-bench/venv-libero/bin/python
export MUJOCO_GL=osmesa
cd $S

# 1) 1a 的验证器：必须仍 20 passed / 0 failed
$PY evobot_settle_probe.py --verify-settle                  # exit 0

# 2) 几何核心自检 + 5 个变异
$PY evobot_geom_wire.py --selftest                          # exit 0
$PY evobot_geom_wire.py --selftest --inject boxrot          # exit 1

# 3) 接线验证 + 变异
$PY evobot_geom_wire.py --verify-wiring                     # exit 0, 13 passed
$PY evobot_geom_wire.py --inject-wiring rbound              # exit 1

# 4) 六个反例（f 目前是红的，这是真回归）
$PY evobot_geom_counterexample_probe.py                      # exit 1, X6 FAIL
$PY evobot_geom_counterexample_probe.py --inject lift       # exit 1, X5 FAIL

# 5) 配对对比（只读 raw JSON，不跑仿真）
$PY evobot_extent_pair_report.py /tmp/legacy_out /tmp/wired_out   # exit 0
```

实跑命令（串行，每个约 1–2 分钟）：

```bash
# 新几何（工作区脚本）
cd $S
LIBERO_SUITE=libero_object LIBERO_TASK=2 LIBERO_OUT=/tmp/wired_out/x.json \
  $PY evobot_libero_geom.py

# 旧几何（/tmp/legacy 里是改动前的冻结副本，用于配对对照）
cd /tmp/legacy
LIBERO_SUITE=libero_object LIBERO_TASK=2 LIBERO_OUT=/tmp/legacy_out/x.json \
  $PY evobot_libero_geom.py
```

---

## 13. 明确不宣称

- **不宣称** 抓取成功率提升。实测 7 个实例：1 个由过变不过，0 个由不过变过。
- **不宣称** 几何修正就能解决 B2。「1b 修好了公式」= 测量正确了；抓不抓得住是策略问题，
  第 9 节已经证明两者可以分离（同样正确的 extent，一个过一个不过）。
- **不宣称** 已独立验证。13 项接线检查、6 个反例、所有变异都是**我自己写、自己跑**。
  标为 **Simulation Tested**。唯一够得上 Independently Verified 的是第一阶段那条
  「离线 XML 路径 vs 在线 sim 路径 18/18 逐位相同」（两条独立代码路径互证）。
- **不宣称** 覆盖全部 LIBERO 物体。几何只测了 `libero_object` 的 5 个 + bowl，共 6 个。
  `libero_10` / `libero_90` 的物体**没测**。
- **不宣称** 修复了 `evobot_geom_true.py` / `evobot_v2.py`。按裁决保留墓碑。

