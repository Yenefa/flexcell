# EvoBot 论文 v0.2 · 研究协议包（#251）

> **状态：DRAFT v0.1.2 — 未冻结，未执行。**（v0.1.1 回填接口差异表；v0.1.2 记录 #249 封印评估器源码的交叉核对，见 ASSUMPTIONS.md §5）
> 本目录只包含协议、任务定义、槽位清单与判读规则，**没有任何一条实验记录**。
> 24 个槽位初始状态全部为 `NOT_RUN`。本文档出现的每个数字，要么是**计划参数**，
> 要么是**历史证据**（标注为「历史」，且声明不可合池），没有第三种。

## 1. 这个包要回答什么

在**固定用户目标 + 人工注入缺陷**的受控条件下，四类信息供给（无反馈 / 真实执行反馈 /
失配反馈 / 真实反馈 + 显式指导）对「自主修复成功率」各自起什么作用。
完整问题陈述与假设见 [PROTOCOL.md](PROTOCOL.md) §1。

## 2. 边界声明（先读这段，再看任何表格）

| # | 声明 |
| --- | --- |
| B1 | 本包**没有执行任何实验**：不调用模型、不启动 ROS/Gazebo、不联网、不产生运行目录。 |
| B2 | 全部 24 槽位为 `NOT_RUN`；[RUN_MANIFEST.md](RUN_MANIFEST.md) 的状态列是权威计数。 |
| B3 | 历史 W5/E2 系列结果（E2b `3/3`、E2d `6/6`、E2e `3/3`、Level B `2/2`，以及 E2 `0/3`、E2c `0/2`、Level C `0/2`）在本包内**一律标注为「历史」**。它们产出于不同的 harness 身份、不同模型、不同预算、不同缺陷注入实现，**不可与 v0.2 合池**，也不得被复述为「已达成的可靠性」。 |
| B4 | 历史分数只用于解释**设计动机**（例如「显式指导看起来会改变是否落笔」），不作为 v0.2 的基线数值、预期值或比较基准。 |
| B5 | 依赖 #249 / #250 的接口写成**计划接口**（[ASSUMPTIONS.md](ASSUMPTIONS.md)），不写成已实现。 |
| B6 | 本包不改历史证据、不改冻结评估器、不改阈值、不改正式基线。 |
| B7 | `n=3` 是**探索性**规模：不做显著性检验、不报置信区间、不做跨任务族泛化声明。 |

## 3. 全包状态词（统一口径）

| 词 | 含义 | 本包当前是否出现 |
| --- | --- | --- |
| `DRAFT` | 草案，评审可改 | 是（全部文档） |
| `TBD` | 参数未定；字段填 `TBD`，并在同处注明「由谁填」 | 是 |
| `DRAFT-FIXED` | 本版本内的设计选择，不随手改；要改须在 [PROTOCOL.md](PROTOCOL.md) §8 偏差表登记并升版本 | 是 |
| `FROZEN` | 参数写死；改任一参数即视为新版本 | **否**（v0.1 尚未冻结任何实验参数） |
| `NOT_RUN` | 槽位未派发 | 是（24 / 24） |
| `已执行` | 存在证据链的运行 | **否 —— 本包不存在这个状态** |

## 4. 与 #248–#254 的对应

| issue | 内容 | 本包对应位置 | 状态 |
| --- | --- | --- | --- |
| [#248](https://github.com/Yenefa/flexcell/issues/248) | 论文 v0.2 父任务 | 全包 | DRAFT 子集 |
| [#249](https://github.com/Yenefa/flexcell/issues/249) | 反馈读取通道的信息边界 | [ASSUMPTIONS.md](ASSUMPTIONS.md) §2（计划接口）；[PROTOCOL.md](PROTOCOL.md) §2 条件 A 的可达性前提 | 未验收 → 开工前提 |
| [#250](https://github.com/Yenefa/flexcell/issues/250) | 固定任务约束与验收负例契约 | [TASKS.md](TASKS.md) §5（计划接口）；[PROTOCOL.md](PROTOCOL.md) §7 判定 | 未验收 → 开工前提 |
| **#251** | **本协议包** | **本目录 8 份文档 + 1 个离线自检脚本** | **DRAFT v0.1** |
| [#252](https://github.com/Yenefa/flexcell/issues/252) | 执行实验 | [RUN_MANIFEST.md](RUN_MANIFEST.md) 的槽位与状态列；[ADMISSION.md](ADMISSION.md) 准入清单 | 未开始 |
| [#253](https://github.com/Yenefa/flexcell/issues/253) | 保留场景 | [TASKS.md](TASKS.md) §4 回归场景清单与保留规则 | 未开始 |
| [#254](https://github.com/Yenefa/flexcell/issues/254) | 论文更新 | [ANALYSIS.md](ANALYSIS.md) §6 报告模板（预先声明口径） | 未开始 |

## 5. 目录导航

| 文件 | 回答什么 | 谁维护 |
| --- | --- | --- |
| [PROTOCOL.md](PROTOCOL.md) | 研究问题、4 条件、2 任务族、24 槽矩阵、预算、停止条件、偏差规则 | #251（本包） |
| [TASKS.md](TASKS.md) | 两个任务族的不可变目标 / 对象集合 / 容差 / 允许改的字段 / 回归场景 | #251 起草，#253 补回归场景 |
| [RUN_MANIFEST.md](RUN_MANIFEST.md) | 24 个槽的清单表；状态列权威 | #251 建表，#252 逐条回填 |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | 每个字段的定义、单位、以及三种分母的口径 | #251 |
| [ANALYSIS.md](ANALYSIS.md) | 预先声明的主对比与次要对比、错误接纳/错误拒绝的算法、进表规则 | #251 声明，#254 引用 |
| [ADMISSION.md](ADMISSION.md) | 开工前必须满足的准入项与证据字段 | #251 起草，#252 逐项签字 |
| [ASSUMPTIONS.md](ASSUMPTIONS.md) | 依赖 #249 / #250 的**计划接口**、版本化契约、拒绝理由码 | #251 起草，#249/#250 落定后回填 |
| `check_protocol_docs.py` | 离线自检：文件齐全、24 槽全 NOT_RUN、无「已执行」断言 | #251 |

## 6. 离线自检（可执行，无需网络 / 模型 / ROS）

在仓库根目录执行：

```bash
python3 docs/research/evobot-paper-v02/check_protocol_docs.py
```

预期输出（全通过，退出码 0）：

```
[ OK ] required files: 8/8
[ OK ] manifest slots: 24 rows, 24 unique ids
[ OK ] matrix coverage: 2 families x 4 conditions x 3 repetitions = 24
[ OK ] slot status: 24 NOT_RUN, 0 terminal
[ OK ] status counts: declared NOT_RUN=24, rows=24
[ OK ] claim scan: no executed-run assertion found
[ OK ] boundary marker: historical scores carry 不可合池 note
[ OK ] doc shape: 8 docs carry DRAFT + 已知限制
PASS
```

**拒绝的例子**：把任一槽位状态改成 `SUCCESS_VERIFIED` 后重跑，
脚本必须以退出码 1 失败：

```
[ FAIL ] slot status: 23 NOT_RUN, 1 terminal
FAIL: 1 check(s) failed
  - [slot status] non-NOT_RUN slots: F1-A-r1=`SUCCESS_VERIFIED`
```

同理，删掉一份文件、去掉某行的「历史」标记、或写进一条声称实验跑完的断言，
都会以退出码 1 失败。**反面示例必须写在代码块里**——写在正文里同样会被扫到：

```
实验已完成，24/24 成功。        <- claim scan 会拒绝这一行
```

`claim scan` 只扫**代码围栏之外**的正文，所以本段演示是安全的；
把同样的句子写进 PROTOCOL.md 正文会被判失败（见上一条拒绝示例）。

该脚本只读本目录、纯 stdlib、退出码 0/1。它检查的是**文档层的自我一致性**，
不是实验正确性 —— 协议自检通过不等于实验可做，也绝不构成任何能力证据。

## 7. 已知限制

- 本包是**草案**：预算上限、批次总额度、运行窗口、模型身份、seed 具体值均为 `TBD`，
  由 #252 在准入阶段填写并在 [ADMISSION.md](ADMISSION.md) 签字后才升 `FROZEN`。
- 两个任务族各只有**一个**缺陷机制（见 [TASKS.md](TASKS.md) §2、§3），
  因此本设计测的是「这两个机制上的修复行为」，不是「一般修复能力」。
- 派发顺序固定且串行（见 [RUN_MANIFEST.md](RUN_MANIFEST.md) §3），存在时间漂移混淆；
  已在 [PROTOCOL.md](PROTOCOL.md) §9 列明，不做事后校正性分析。
- [ASSUMPTIONS.md](ASSUMPTIONS.md) 依赖的两个接口在 base `2ca40ebe` 上**尚不存在**
  （`benchmark/repair_eval/` 目录缺失），因此本包的判定流程目前**不可端到端执行**。
