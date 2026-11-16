# RUN_MANIFEST — 24 槽运行清单（v0.1 草案）

> **状态：DRAFT v0.1。未冻结。未执行。**
> 下表 `状态` 列是**权威计数**：当前 24 行全部为 `NOT_RUN`，终态 0 行。
> `seed` 与 C 条件的 `donor` 为 `TBD`，填写责任见 §2。
> 本表不是运行记录，也没有任何一行代表跑过一次。

## 1. 槽位表（2 族 × 4 条件 × 3 重复 = 24）

| # | slot_id | 任务族 | 缺陷实例 | 条件 | 重复 | seed | donor（仅 C） | 派发批次 / 序 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `F1-A-r1` | F1 | `DEF-F1-REG` | A | r1 | `5101` | — | 批 1 / 序 1 | `BUDGET_EXHAUSTED` |
| 2 | `F2-A-r1` | F2 | `DEF-F2-MAP` | A | r1 | `5201` | — | 批 1 / 序 2 | `BUDGET_EXHAUSTED` |
| 3 | `F1-B-r1` | F1 | `DEF-F1-REG` | B | r1 | `5101` | — | 批 1 / 序 3 | `UNKNOWN` |
| 4 | `F2-B-r1` | F2 | `DEF-F2-MAP` | B | r1 | `5201` | — | 批 1 / 序 4 | `BUDGET_EXHAUSTED` |
| 5 | `F1-C-r1` | F1 | `DEF-F1-REG` | C | r1 | `5101` | `F1-B-r2` | 批 1 / 序 5 | `UNKNOWN` |
| 6 | `F2-C-r1` | F2 | `DEF-F2-MAP` | C | r1 | `5201` | `F2-B-r2` | 批 1 / 序 6 | `BUDGET_EXHAUSTED` |
| 7 | `F1-D-r1` | F1 | `DEF-F1-REG` | D | r1 | `5101` | — | 批 1 / 序 7 | `UNKNOWN` |
| 8 | `F2-D-r1` | F2 | `DEF-F2-MAP` | D | r1 | `5201` | — | 批 1 / 序 8 | `UNKNOWN` |
| 9 | `F2-D-r2` | F2 | `DEF-F2-MAP` | D | r2 | `5202` | — | 批 2 / 序 9 | `BUDGET_EXHAUSTED` |
| 10 | `F1-D-r2` | F1 | `DEF-F1-REG` | D | r2 | `5102` | — | 批 2 / 序 10 | `UNKNOWN` |
| 11 | `F2-C-r2` | F2 | `DEF-F2-MAP` | C | r2 | `5202` | `F2-B-r1` | 批 2 / 序 11 | `BUDGET_EXHAUSTED` |
| 12 | `F1-C-r2` | F1 | `DEF-F1-REG` | C | r2 | `5102` | `F1-B-r1` | 批 2 / 序 12 | `UNKNOWN` |
| 13 | `F2-B-r2` | F2 | `DEF-F2-MAP` | B | r2 | `5202` | — | 批 2 / 序 13 | `BUDGET_EXHAUSTED` |
| 14 | `F1-B-r2` | F1 | `DEF-F1-REG` | B | r2 | `5102` | — | 批 2 / 序 14 | `UNKNOWN` |
| 15 | `F2-A-r2` | F2 | `DEF-F2-MAP` | A | r2 | `5202` | — | 批 2 / 序 15 | `UNKNOWN` |
| 16 | `F1-A-r2` | F1 | `DEF-F1-REG` | A | r2 | `5102` | — | 批 2 / 序 16 | `UNKNOWN` |
| 17 | `F1-A-r3` | F1 | `DEF-F1-REG` | A | r3 | `5103` | — | 批 3 / 序 17 | `UNKNOWN` |
| 18 | `F2-A-r3` | F2 | `DEF-F2-MAP` | A | r3 | `5203` | — | 批 3 / 序 18 | `BUDGET_EXHAUSTED` |
| 19 | `F1-B-r3` | F1 | `DEF-F1-REG` | B | r3 | `5103` | — | 批 3 / 序 19 | `UNKNOWN` |
| 20 | `F2-B-r3` | F2 | `DEF-F2-MAP` | B | r3 | `5203` | — | 批 3 / 序 20 | `BUDGET_EXHAUSTED` |
| 21 | `F1-C-r3` | F1 | `DEF-F1-REG` | C | r3 | `5103` | `F1-B-r1` | 批 3 / 序 21 | `UNKNOWN` |
| 22 | `F2-C-r3` | F2 | `DEF-F2-MAP` | C | r3 | `5203` | `F2-B-r1` | 批 3 / 序 22 | `BUDGET_EXHAUSTED` |
| 23 | `F1-D-r3` | F1 | `DEF-F1-REG` | D | r3 | `5103` | — | 批 3 / 序 23 | `UNKNOWN` |
| 24 | `F2-D-r3` | F2 | `DEF-F2-MAP` | D | r3 | `5203` | — | 批 3 / 序 24 | `BUDGET_EXHAUSTED` |

**条件含义**：A = 无反馈（等预算重复尝试）；B = 真实执行反馈；C = 失配反馈；
D = 真实反馈 + 显式指导。定义见 [PROTOCOL.md](PROTOCOL.md) §2。

**缺陷实例**：`DEF-F1-REG`（对象注册缺失）、`DEF-F2-MAP`（坐标变换/目标映射）。定义见 [TASKS.md](TASKS.md) §2、§3。

## 2. 空字段的填写责任

| 字段 | 当前值 | 谁填 | 何时填 | 约束 |
| --- | --- | --- | --- | --- |
| `seed` | `TBD` | **#252**（执行负责人） | 准入通过、开工前，一次性写死 | 同一 `(任务族, 重复)` 的**四个条件共用同一 seed**（配对）；不得与 `benchmark/tasks/` 已用区间（train 1000–1011、val 2000–2005、held_out 9000–9005）冲突；填后即 `FROZEN`，改则升版本 |
| `donor`（C 行） | `TBD` | **#252** | 在该族 **B 条件**至少产生一条完整记录之后、任何 C 运行之前 | 必须是同族、同缺陷实例、**不同 seed** 的 B 条件 run_id；绑定后写死；donor 缺失则该 C 槽保持 `NOT_RUN`，不得顶替 |
| `状态` | `NOT_RUN` | **#252** | 每条记录终态确定时 | 只能从 §4 的词表里取；**不得**把 `FAIL` 改写成 `SUCCESS_VERIFIED`，也不得删行 |
| 派发批次 / 序 | 已固定 | — | — | 见 §3，不随运行改变 |
| 记录证据路径 | 表中未列 | **#252** | 每条记录终态时补入运行记录目录 | 路径写进运行记录，不回填本表的其它列 |

## 3. 派发顺序规则（DRAFT-FIXED）

- **批次 = 重复序号**：批 1 = `r1`，批 2 = `r2`，批 3 = `r3`。每批 8 个槽位。
- **批内条件顺序**做反向交替以部分抵消时间漂移：
  批 1 = A→B→C→D，批 2 = **D→C→B→A**，批 3 = A→B→C→D。
- **批内族顺序**同样交替：批 1 = F1→F2，批 2 = **F2→F1**，批 3 = F1→F2。
- **串行**：同一时刻只有一个仿真运行（与 #235 / #247 的串行约定一致，见 [ADMISSION.md](ADMISSION.md) §6）。
- 顺序**固定，不随机**。固定顺序的好处是可审计；代价是残余时间漂移混淆，已在
  [PROTOCOL.md](PROTOCOL.md) §9 L4 声明，**不做**事后校正性分析。

## 4. 状态词表（只允许这些值）

| 状态 | 含义 | 进哪个分母 |
| --- | --- | --- |
| `NOT_RUN` | 未派发 | 不进任何分母 |
| `RUNNING` | 已派发、未终态 | 临时态，终态确定后必须替换 |
| `SUCCESS_VERIFIED` | G1–G4 全通过（[PROTOCOL.md](PROTOCOL.md) §7） | 修复运行数分子 |
| `FAIL` | 任一 G 门失败 | 修复运行数分母 |
| `BUDGET_EXHAUSTED` | 达 6 次交互 / 20,000 tokens 上限 | 修复运行数分母（**不算成功**） |
| `UNKNOWN` | 无法判定（未确认动作终态、证据不足） | 单列，**不并入失败率分子** |
| `INVALID` | 证据无效（信息边界失守、donor 不匹配、环境失效） | **不进任何分母** |

## 5. 补跑与 NOT_RUN 规则（DRAFT-FIXED）

1. 剩余槽位一律 `NOT_RUN`：因 S1–S4 停止（[PROTOCOL.md](PROTOCOL.md) §6）而未派发的槽位，
   保持 `NOT_RUN` 并在备注写原因。
2. **不用成功补跑替换失败**：已终态的记录不得被覆盖、删除或移出表。
3. 需要重复某槽位时，追加**新行**（slot_id 加 `.re2` 后缀）并说明原因与偏差码；
   原行保留原终态。**新行不与原行合并计数**。
4. 任何新增行都要同步更新 §6 的计数。

> **2026-11-17 第二批（主分析批次）**：题面切到 `task_variant=v2`，48 槽（每格 6 次），535,151 tokens。表中 24 行为其中重复 1–3 的对应槽；重复 4–6 是额外样本，用于把 n 提到 6，单独记录在 `v2_matrix_n6.json`。
>
> **主结论是零结果**：四条件在成功率上分不出来（F1 全过；F2 为 2/2/3/4，A 对 D 的 Fisher p=0.57）。详见 `ANALYSIS.md §6.02`。第一批 v1（题面写出答案）的数据保留在 `real_instances_matrix.json`，不并入。

## 6. 状态计数（随运行更新，当前为初始值）

> **2026-11-17 首次真实派发（head `6d5fd5d`，模型 `deepseek-flash`）：24 槽全部产出记录，合计 144,133 tokens。seed 已按 (族, 重复) 配对写入，C 的 donor 为同族另一 seed 的 B 记录。
>
> 三条必须随表读的说明：
> 1. **派发顺序与 §3 不同**：实际按「族 × 条件 × 重复」推进，而不是 §3 的批次交错顺序。原因是 C 需要同族不同 seed 的 B 记录先存在，§3 的顺序在执行到 C-r1 时还没有 B-r2。这是对预登记顺序的偏差，登记在此。
> 2. **`BUDGET_EXHAUSTED` 不等于修复失败**：终态取自 agent 是否宣告完成，门判定独立于它。例如 F2-A-r2 耗尽但门判 PASS；F1-D-r3 同样。逐槽的门结论见 `evidence/real_instances_matrix.json`。
> 3. **没有一条是 `SUCCESS_VERIFIED`**：独立裁决门（G3）从未运行，契约门的 PASS 只能记 `UNKNOWN`。


> **2026-11-17 首次真实派发（head `6d5fd5d`，模型 `deepseek-flash`）：24 槽全部产出记录，合计 144,133 tokens。seed 已按 (族, 重复) 配对写入，C 的 donor 为同族另一 seed 的 B 记录。
>
> 三条必须随表读的说明：
> 1. **派发顺序与 §3 不同**：实际按「族 × 条件 × 重复」推进，而不是 §3 的批次交错顺序。原因是 C 需要同族不同 seed 的 B 记录先存在，§3 的顺序在执行到 C-r1 时还没有 B-r2。这是对预登记顺序的偏差，登记在此。
> 2. **`BUDGET_EXHAUSTED` 不等于修复失败**：终态取自 agent 是否宣告完成，门判定独立于它。例如 F2-A-r2 耗尽但门判 PASS；F1-D-r3 同样。逐槽的门结论见 `evidence/real_instances_matrix.json`。
> 3. **没有一条是 `SUCCESS_VERIFIED`**：独立裁决门（G3）从未运行，契约门的 PASS 只能记 `UNKNOWN`。


| 状态 | 计数 |
| --- | --- |
| `NOT_RUN` | 0 |
| `RUNNING` | 0 |
| `SUCCESS_VERIFIED` | 0 |
| `FAIL` | 0 |
| `BUDGET_EXHAUSTED` | **11** |
| `UNKNOWN` | **13** |
| `INVALID` | 0 |
| 合计 | 24 |

> 此计数与 [README.md](README.md) §6 的离线自检一致：脚本会核对「24 行、24 个唯一 id、
> 状态列全是 `NOT_RUN`、覆盖 2×4×3 全组合」。任何一次回填若不更新本节，自检会失败。

## 7. 已知限制

- **合成 fixture 的跑批不能顶替本表的槽位。** `experiments/repair_eval_v02/` 里有一套合成 fixture（`skill/registry.py`、`skill/mapping.py`），它验证的是跑批机制本身，不是 `DEF-F1-REG` / `DEF-F2-MAP`。用它跑出的记录（`evidence/real_matrix.json`、`confirmatory_f1bc.json`）在结论表里按 stand-in 标注，**本表 24 行的状态不得据此改动**。
- 本表槽位的 `seed` 仍为 `TBD`：只有对真实缺陷实例的批才填，填了就要能对着 `DEF-*` 的注入文件复现。


- 表里**一个运行结果都没有**；`NOT_RUN` × 24 就是当前全部事实。
- 派发顺序固定且串行，存在残余时间漂移混淆（§3）。
- C 条件的 donor 绑定存在**结构性依赖**：批 1 的 C 行必须等对应族的 B 条件先出结果，
  因此实际派发顺序会在批 1 内被这段依赖打乱；打乱后的真实顺序必须记进运行记录，
  并在此表备注说明，**不得**因此修改 §3 的声明顺序。
- `seed` 未定 → 本表目前**不构成可执行计划**，只构成待填清单。