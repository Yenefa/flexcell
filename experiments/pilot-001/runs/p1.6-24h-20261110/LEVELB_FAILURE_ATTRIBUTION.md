# Level B 失败归因（2026-11-10，Flash 三次）

| 运行 | 轮数 | tokens | 是否修改源码 | 结果 |
| --- | --- | --- | --- | --- |
| r1 | 6 | 10124 | 否 | 失败（judge 构建重复包 bug，已修复；agent 也未编辑） |
| r2 | 6 | ~ | 否 | 失败（重复 list_dir/read_file，无 edit） |
| r3 | 6 | ~ | 否 | 失败（重复 run_checks/run_execution/read_file，无 edit） |

## 观察
- 三次都在**读取/执行**上耗尽 6 轮，从未调用 `edit_file`/`write_file`；
- r3 已提供 `search_code` 工具与"必须编辑"的 Level B 指令，仍未触发写操作；
- 缺陷基线有效：`dual_object` ROBOT_FAILURE、`normal`/`regrasp` PASS、build OK；
- judge 三门在 VM 重置后稳定 PASS（对照 probe）。

## 归因
- **模型工具选择/行动执行能力**（Flash 在该代码修复任务上不写文件）；
- 任务设计：基线有效、缺陷单点、有 search_code，不认为是任务不可解；
- 环境：已排除（基线可跑、judge 稳定）。

## 下一步假设
- 换更强模型（v4-pro）单次尝试，检验"模型能力"假设；
- 若仍不写：改进 Agent 脚手架（强制首步 search_code、限制读取次数、要求 edit 后再执行）。
