# EvoBot 论文 v0.2 — 稿件工作区（#254）

> 本文件是**稿件侧**索引。协议包的总索引是同一目录下的 `README.md`（#251 所有）。
> 两者分开命名，是因为它们由不同任务并行提交，同名会在合并时产生 add/add 冲突。

> **状态：DRAFT。已有探索性模型记录；核心效果不可判定。**
> 本目录包含可复算的历史数字、探索记录的结论—证据对应表、
> 字段语义澄清、以及与 #252/#253 的接口。等 #252（对照）与 #253（保留场景）产出原始
> 记录后，才填表、才写正文。

## 为什么先做这一层

#254 的验收条件里，有三条**不依赖**新实验就能做，而且必须先做，否则等结果出来时会重复
v0.1 的老问题（先有结论、后找证据）：

1. **可复算**：v0.1 引用的 6/6、3/3、0/3、0/2 来自 `aggregate.json`——那是由产出运行的同一个
   循环写的。本轮把它们从**每条运行的记录**重算了一遍，见 [HISTORICAL_V01.md](HISTORICAL_V01.md)。
2. **口径分离**：历史（v0.1，受指导配置修复）与本轮（v0.2，反馈对照）必须分开叙述、不可合池。
3. **字段语义**：`claim_success` / `false_success` 在旧记录里的真实分布与局限，避免继续用
   一个恒定字段去证明"验证有效"。

## 目录

| 文件 | 作用 | 依赖实验结果 |
| --- | --- | --- |
| [PAPER_INDEX.md](PAPER_INDEX.md) | 状态、边界、与 #252/#253 的接口（本文件） | 否 |
| [HISTORICAL_V01.md](HISTORICAL_V01.md) | v0.1 历史数字的**重算**与适用范围 | 否 |
| [INTEGRATION_SEAM.md](INTEGRATION_SEAM.md) | #249 与 #250 的接缝实测与适配器契约 | 否 |
| [CLAIMS_EVIDENCE_TABLE.md](CLAIMS_EVIDENCE_TABLE.md) | 一页结论—证据对应表（骨架，行待填） | 是 |
| [FIELD_SEMANTICS.md](FIELD_SEMANTICS.md) | `claim_success` 等字段的实际含义与误用 | 否 |
| [METHOD.md](METHOD.md) | 方法：仪器怎么造、为什么这么造，以及它不能支持什么 | 否 |
| [tools/recompute_w5_archive.py](tools/recompute_w5_archive.py) | 重算脚本（纯 stdlib，只读归档） | 否 |
| `archive_recompute.json` | 上一条的原始输出 | 否 |

## 边界声明

- 本目录没有独立成功率、显著性或泛化结论；探索门判数不作为能力成功率。
- 历史数字只用于**设计动机**与**方法对照**，不参与 v0.2 的任何统计口径。
- 复算脚本读取归档、写出新文件，不改动任何历史记录；`setup/acceptance/` 与
  `experiments/pilot-001/runs/` 保持原样。
- 论文 / 计划书 / PPT 必须使用同一套口径；本目录是唯一口径来源，三者引用它而不是各自记账。

## 与 #252 / #253 的接口

| 上游 | 需要提供 | 本目录用它填什么 |
| --- | --- | --- |
| #252 对照运行 | 24 槽的原始记录、每条判定、用量、端到端时间 | [CLAIMS_EVIDENCE_TABLE.md](CLAIMS_EVIDENCE_TABLE.md) 的主表；`ANALYSIS.md` 的 B vs A |
| #253 保留场景 | 6 槽的候选 SHA、运行清单、回归记录 | 同一张表的"保留场景"段 |
| #249 / #250 | `policy_id` + `fingerprint`；`contract schema/version/sha256`；理由码 | 每条记录的"身份"列 |

现有 R1–R4 仅登记已产生的探索记录，不替代独立验收。表格事实与源码身份可用 `tools/check_paper_evidence.py` 核对。

## 作者与授权

作者、单位、贡献声明、授权信息**尚未提供**，本目录不做假设，也不代填。见
[CLAIMS_EVIDENCE_TABLE.md](CLAIMS_EVIDENCE_TABLE.md) §4 的待填清单。
