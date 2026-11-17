# RUN_MANIFEST — 登记计划与 v2 历史运行台账（DRAFT）

> **状态：DRAFT；未形成正式准入凭据。** 表中顺序/seed/donor 是登记输入，状态列仅绑定
> `evidence/v2_matrix_n6.json` 的 r1–r3；不能与 v1 的 `real_instances_matrix.json` 对账。
> v2 来源源码 `31541278f2a3abea2d89b69eb48f7e84859e2ae2`；额外 r4–r6 共24条明确单列。
> 本表的存在不证明实验条件合规，主比较仍不可判定。

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

## 2. 版本与字段

- 每个槽位固定 slot_id、seed、donor 和登记序号。运行器读取本表或显式版本化 JSON 计划，
  对子集也保留登记顺序，并将原计划与摘要归档；未登记的新重复必须先提供新计划。
- 历史 seed 只是标签，实际实例输入未随其变化；不将标签解释为不同初态或独立任务。
- C 只使用登记的 B donor。若其尚未完成或原始日志缺失，该槽 NOT_RUN，不临时借用其他来源。
- 原计划 C-r1 依赖尚未产生的 B-r2，这是原登记的依赖缺口。执行前须在新版本中解决；
  实现不得为了补满槽位自行改顺序或 donor。

## 3. 派发顺序规则（原登记保留）

批次按重复序号；r1/r3 为 A→B→C→D、F1→F2，r2 为 D→C→B→A、F2→F1。
旧批次实际上按族→条件→重复推进，因此存在顺序偏差。本修补不把历史偏差改写成合规执行。

## 4. 状态词表

NOT_RUN、RUNNING、SUCCESS_VERIFIED、FAIL、BUDGET_EXHAUSTED、UNKNOWN、INVALID。
源码门 PASS 不等于 SUCCESS_VERIFIED；G3 未执行时不产生独立成功率。

## 5. 失败、停止与补跑

失败和异常全部保留；停止后的剩余槽位 NOT_RUN。补跑是新版本/新记录，不覆盖旧行。
旧 v1、v2 主批次和后续新计划分别留账，不能按相同 slot_id 混成同一批。

## 6. 状态计数（仅 v2 主批次的 r1–r3）

| 状态 | 计数 |
| --- | --- |
| `NOT_RUN` | **0** |
| `RUNNING` | **0** |
| `SUCCESS_VERIFIED` | **0** |
| `FAIL` | **0** |
| `BUDGET_EXHAUSTED` | **11** |
| `UNKNOWN` | **13** |
| `INVALID` | **0** |
| 合计 | 24 |

完整 v2 为28 UNKNOWN、20 BUDGET_EXHAUSTED；35/48 为源码/配置门计数。
原始 JSON 的字节不改。历史顺序偏差与额外槽位通过对账输出显式列出，不能只展示“状态一致”。

## 7. 已知限制

协议仍 DRAFT。F1 静态答案、历史 D 指导缺失、seed 不改变实例、G3 未运行以及真实模型
保留集未执行，均保留为限制；“零结果/四组相同”的旧结论已撤回。#247 来源与窗口由
zyx-dc 在 #265 补齐；主机/构建凭据可作为环境来源，不要求镜像。
