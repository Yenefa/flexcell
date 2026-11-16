# 结论 — 证据对应表（v0.2 骨架，行待填）

> **状态：DRAFT。主表 0 行。** 这是刻意的：本表只允许填入**有原始记录支撑**的行。
> 在 #252 / #253 交付之前，填任何行都等于编造。

## 1. 主表

| # | 结论（一句话） | 研究问题 | 分组 | 单位 | 分子/分母（D1/D2/D3） | 源码 SHA | 模型 / 协议身份 | 证据位置 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | F1 族、B 条件（真实执行反馈）：2 次重复均被契约门判 `ACCEPT` | 反馈类型是否影响是否修好 | B | D1 | 分子 2 / 分母 0（终态 `UNKNOWN`，不入 D1） | `5458f1d` | `deepseek-flash`；`a48651c0…`；`flexcell.repair_eval.task_contract/1` v1 `6628e64f…` | `experiments/repair_eval_v02/evidence/confirmatory_f1bc.json`（F1-B-r1/r2） | `UNKNOWN` |
| R2 | F1 族、C 条件（失配反馈）：2 次重复均被判 `ACCEPT`，donor 为同族另一 seed 的 B 记录 | 不匹配的反馈是否足以支持修复 | C | D1 | 分子 2 / 分母 0（同上） | `5458f1d` | 同上；donor `F1-B-r2`（seed 5102）、`F1-B-r1`（seed 5101） | `confirmatory_f1bc.json`（F1-C-r1/r2）+ `evidence/donor/*.log` | `UNKNOWN` |

**为什么这两行不是 `SUPPORTED`**：契约门判了 `ACCEPT`，但**独立裁决门从未运行**（`gate_independent = NOT_RUN`），所以终态一律 `UNKNOWN`，按 §3 的分母规则不进 D1。把它们写成 `SUPPORTED` 就等于把「契约说对了」当成「独立复核说对了」，这正是本表要防的事。独立门需要 #253 的 6 个保留场景跑起来。

**这 4 条记录满足的身份条件**：源码 `5458f1d`（提交后才跑的批）、配对 seed（5101/5102，四条件共用）、C 的 donor 是同族**不同 seed** 的 B 记录且在任何 C 运行之前绑定、模型 `deepseek-flash`、策略指纹、契约 schema/version/sha256。缺一项都不能进表。

**24 槽探索批（`real_matrix.json`）为什么不在主表**：那一批没有记录 seed（当时的 `build_candidate` 根本不接受 seed，三次重复其实是同一个输入）、C 的 donor 是合成文本、且运行时代码尚未提交因而没有源码 SHA。它作为**探索性观测**保留在 `experiments/repair_eval_v02/README.md`，不构成结论行。

填写规则：

- **一行一个结论**，不允许一行里塞两个判断。
- 分母必须写明是 D1（修复运行数）、D2（候选执行数）还是 D3（最终场景数）；三者不混用。
- "身份"列必须同时有：源码 40 位 SHA、模型 id、协议版本（`policy_id` + `fingerprint`、
  `contract schema/version/sha256`）。缺一项即该行状态为 `UNKNOWN`，不得标 `SUPPORTED`。
- 失败、`UNKNOWN`、`NOT_RUN` 的行**也要进表**，不能只列成功。

## 2. 历史段（v0.1，已重算，不可与主表合池）

| # | 结论 | 身份 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| H1 | 受指导配置下，W5-E2d 的 6 条修复记录全部通过目标门与回归门 | `2ca40ebe` 归档，`deepseek-chat`，v0.1 协议 | `experiments/pilot-001/runs/p1.5-w5e2d-20261109/`；重算见 [HISTORICAL_V01.md](HISTORICAL_V01.md) §3 | `HISTORICAL` |
| H2 | W5-E2b 与 W5-E2e 各 3/3 通过 | 同上 | 同上 | `HISTORICAL` |
| H3 | W5-E2（3 轮预算）0/3、W5-E2c（多场景）0/2 | 同上 | 同上 | `HISTORICAL` |
| H4 | agent 自述成功字段在 19 条记录中恒为 false | 同上 | [FIELD_SEMANTICS.md](FIELD_SEMANTICS.md) §2 | `HISTORICAL` |

历史段的作用只有一个：说明 v0.2 为什么要做这个对照。它**不参与**主表的任何比例计算。

## 3. 方法段（不依赖运行结果，可先定稿）

| # | 结论 | 证据 | 状态 |
| --- | --- | --- | --- |
| M1 | 无反馈条件无法读取裁决、遥测、诊断、隐藏答案，也拒绝继承旧运行产物 | #249 的 49 个用例 + `--demo` 输出（PR #257） | `SUPPORTED (synthetic)` |
| M2 | 修复是否通过由冻结契约判定，不读候选自述，也不读候选声明的目标/阈值 | #250 的 7 例语料、109 个用例，false_accept/reject = 0/0（PR #258） | `SUPPORTED (synthetic)` |
| M3 | 协议把 24 个槽位、停止条件与偏差规则固定在执行之前 | `docs/research/evobot-paper-v02/` 自检 PASS（PR #256） | `SUPPORTED (document)` |

"合成"必须写进正文：M1/M2 证明的是**判定逻辑**，不是机器人能力。

## 4. 待作者提供（不代填）

- [ ] 作者列表、单位、贡献声明
- [ ] 授权与署名顺序
- [ ] 论文/计划书/PPT 的当前版本文件位置
- [ ] 目标投稿或提交渠道（决定篇幅与格式）

在这些信息到位前，本表与正文都保持 `DRAFT`。
