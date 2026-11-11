# 独立审计的两条 P0：都已复现、都已修

外部审计指出两处 P0。**我先把两条都复现成可测量的事实，再动手**——采信断言和否认断言一样不合规。

---

## P0-1：T08 首推脚本的 `pkill` 会杀掉几乎一切

### 原代码

```bash
for n in carry_server pick_server ...; do pkill -9 -f "[$n]" 2>/dev/null; done
```

`"[$n]"` 展开成 `[carry_server]`——那是**正则字符类**，匹配 c/a/r/y/_/s/e/r/v 中任意**一个字符**。

### 实测（不是推断）

| 模式 | 对 4 条无关命令行的命中 |
| --- | --- |
| `[carry_server]` | **4 / 4** |
| `[c]arry_server` | **0 / 4** |

若脚本执行，会杀掉 Baseline A 批次进程、shell，可能连 WSL 会话本身。

### 处置

1. **立即杀掉等待中的链条**（`603383`），T08 未执行（证据目录不存在），批次进程 `551958` 存活。
2. 双重防线重写：
   - 栈用 `setsid` 启动 → 整棵树共用一个 PGID，**按进程组杀，不做名字匹配**
   - 名字兜底只把**首字符**加括号（`[c]arry_server`），并在开火前**检查命中数**：≥40 直接拒绝并报错
3. 增加 `--match-test`：**只打印会命中什么，不杀任何进程**

### 非破坏性验证结果

```
pattern                         matches  sample
[c]arry_server                       1  /usr/bin/python3 /home/ros/flexcell-p14-...
[p]ick_server                        1  ...
[o]bserve_server                     1  ...
[t]ask_fsm_server                    1  ...
```

每个模式只命中 1 个进程，且是正确的那个。

---

## P0-2：`push` 子句无法区分推与抓-搬-放（False Success 结构洞）

### 原实现只检查终态

位移在带内、`|Δz| ≤ 20mm`、方向余弦、目标区——**全部来自终态**。

### 反例（审计给出，我实测复现）

起点 `(0.22, 0, 0.0175)`，终点 `(0.16, 0, 0.0175)`：

```
passed = True
  OK  unmoved:target_box_b | distance_m 0.0
  OK  push:target_box_a    | displacement 0.06, vertical 0.0, cos 1.0, zone_dist 0.0
```

**这个终态由「推」和由「抓起来、搬过去、放下」产生的结果完全相同。**
验收器只看终态，因此**结构上无法执行任务里的「禁止抓取」**。

这不是边界情况——我此前的干跑把同一终态记为**合法 PASS**。

### 修复：换证据来源，不是收紧阈值

`evaluate.py` **v0.3.0 → v0.4.0**，push 子句新增轨迹证据：

- 读取 `final_state.trajectory.<object>.max_z_m`（整个运动过程中物体的最大高度）
- 判据：`max_z_m - start_z <= max_lift_during_m`（默认 **5 mm**）
- **缺失轨迹即判 False**（fail closed）：没有「物体没被抬起」的证据，不等于它没被抬起

**没有放宽任何现有阈值。** 30 mm 下界、20 mm 终态高度差、方向余弦 0.9 全部原样保留。
T01–T06 不使用 `push` 子句，**全部冻结结果不受影响**。

### 回归证明：同一输入，两个版本结论相反

```
SAME INPUT (carry-and-place end state, no trajectory)
  start (0.22,0,0.0175) -> end (0.16,0,0.0175)
  v0.3.0 passed = True
  v0.4.0 passed = False
```

### 修复后的完整判据行为

| 用例 | 期望 | 实际 | 依据 |
| --- | --- | --- | --- |
| 真推，抬升 1.0 mm | PASS | **PASS** | `max_lift=0.001` |
| **审计反例：搬过去，无轨迹** | FAIL | **FAIL** | `no trajectory ... cannot prove it was pushed rather than carried` |
| 搬过去，轨迹显示抬升 32.5 mm | FAIL | **FAIL** | `max_lift=0.0325` |
| 抬升恰好 5.0 mm（在上限） | PASS | **PASS** | `max_lift=0.005` |
| 抬升 5.5 mm（超限） | FAIL | **FAIL** | `max_lift=0.0055` |
| 真推但只走 23 mm | FAIL | **FAIL** | 原 30 mm 门保持 |

---

## 这条修复带来的一个真实后果

**T08 现在需要轨迹数据才能判 PASS。** 现有 `capture_ground_truth.py` 只采终态。

所以 T08 实推在轨迹采集接好之前**会判失败**——这是**正确的**：
证明不了是推，就不该记成推成功。

轨迹采集已作为视觉接线任务的一部分派出。

---

## 审计的其他条目：我接受的

| 条目 | 我的判断 |
| --- | --- |
| T08 脚本读 `expected_goal` 定方向/距离 → 是 smoke test，不是 agent 自主 | **接受**。脚本注释里应写明 |
| `gt_before.json` 采了但没用于校验初始位置 | **接受**，应校验 |
| unseen 实例公开在同分支 → 不是严格盲测 | **接受**，措辞需改 |
| A-v2 runner 修复没有版本库实现记录 | **接受**，应提交脚本本体 |
| 首次实推未写 `agent_claimed_success` → 通过时会被记成 `false_failure=True` | **接受**，需修 |
| 孤儿报告「六类节点各 8 个却合计 36」计数不一致 | **接受**，需复核原始证据 |

---

## 审计结论我认同的部分

> 工程实现有实质进展；验收可信度尚未合格；自主开发闭环未验证；跨场景泛化未验证。

**Level 4 Develop 不通过。** 这次审计最有价值的不是它指出的缺陷本身，
而是它证明了：**几千行代码和几十个单元测试，挡不住一行 shell 正则，也挡不住一个定义不完整的判据。**
