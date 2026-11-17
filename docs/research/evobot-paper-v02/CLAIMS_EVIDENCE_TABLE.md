# 结论—证据对应表（DRAFT，2026-11-17 修订）

本表记录已有事实与证据缺口。源码门、模型运行、物理执行和独立验收分别计数。
作者、单位、贡献与授权尚待实际参与者核实；本文件不是投稿或发表证明。

## 1. 探索记录

| # | 记录能支持的事实 | 分母边界 | 执行源码 SHA | 模型 | 原始证据 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | F1-B 的两条合成夹具记录均被契约门接受 | 门判2/2；D1独立成功率不可计算 | `5458f1df6272e9a798e1e8092ffcfdd79829128f` | deepseek-flash | `experiments/repair_eval_v02/evidence/confirmatory_f1bc.json`，F1-B-r1/r2 | SYNTHETIC_EXPLORATORY |
| R2 | 同批 F1-C 的两条合成夹具记录均被契约门接受 | 门判2/2；不构成反馈因果效应 | `5458f1df6272e9a798e1e8092ffcfdd79829128f` | deepseek-flash | 同文件，F1-C-r1/r2；donor为同族另一重复 | SYNTHETIC_EXPLORATORY |
| R3 | v1 的24条源码/配置修复记录：门判22/24，19 UNKNOWN、5 BUDGET_EXHAUSTED | 144,133 tokens；G3全部NOT_RUN；D1不可计算 | `6d5fd5dc92a66aae4be4e51ec0a32da874aff34d` | deepseek-flash | `experiments/repair_eval_v02/evidence/real_instances_matrix.json` | EXPLORATORY |
| R4 | v2 的48条记录：门判35/48，28 UNKNOWN、20 BUDGET_EXHAUSTED | 535,151 tokens；G3全部NOT_RUN；D1不可计算 | `31541278f2a3abea2d89b69eb48f7e84859e2ae2` | deepseek-flash | `experiments/repair_eval_v02/evidence/v2_matrix_n6.json` | EXPLORATORY_NOT_CAUSAL |

R3/R4 的 PASS 仅为源码/配置门，不是机器人任务完成。不同版本、实例与模型不合池。
R4 中 F1 四个标签均6/6；F2 A/B/C/D标签分别2/6、2/6、3/6、4/6。
历史 D 指导实际未送达，A 仍可读静态答案，seed 没改变实例；修补前真实 Agent 的文件读取
也可绕过 A 的反馈隔离。没有逐请求归档，不能追溯判定48条中哪条实际使用过绕过路径。
这些事实不能支持“反馈有效/无效”“四组等效”或“只改变成本”，事后 p 值不作正式结论。

R4 原始字节 SHA-256：`dccc65c785cd243da5a3a7af1821129f8e0375114fb2d635eae6553b0c12028e`。
R3 原始字节 SHA-256：`d260cddeffc6e822ec8127f879bafee5ad47a081c8bbb9e19cd5a958dcdaf51e`。
`RUN_MANIFEST.md` 的状态仅对应R4的r1–r3；额外24槽与历史顺序偏差在对账中显式列出。

## 2. 历史 v0.1（不进入 v0.2 分母）

| # | 历史记录 | 模型与计数 | 来源 |
| --- | --- | --- | --- |
| H1 | 受指导的W5-E2d记录全部通过归档目标/回归门 | deepseek-chat 4/4；deepseek-v4-pro 1/1；deepseek-flash 1/1 | `experiments/pilot-001/runs/p1.5-w5e2d-20261109/` |
| H2 | W5-E2b与W5-E2e的归档通过记录 | E2b：chat 3/3；E2e：chat 2/2、flash 1/1 | 对应归档目录与 `archive_recompute.json` |
| H3 | W5-E2与W5-E2c失败记录 | E2：chat 0/3；E2c：chat 0/2 | 对应逐条result.json |
| H4 | 19条归档中的claim_success与false_success字段均为false | FCAgent适配器固定输出，不能解释为模型自评行为 | `FIELD_SEMANTICS.md` |

旧6/6与3/3仅为受指导的历史可行性材料，不声称反馈增益或通用可靠性。

## 3. 方法与当前边界

- #249：类别/真实路径/别名隔离与真实Agent接线有离线负例；不能据此补认历史批次合规。
- #250：七例合成语料、唯一回归身份、冻结目标判定；合成错误接纳/拒绝计数不代表物理真值。
- #251/#252：运行器按登记计划冻结顺序、seed与donor；缺失donor保持NOT_RUN，历史偏差保留。
- #253：冻结与参考比较已有源码门入口，真实模型候选的物理保留集、初态与普通回归仍NOT_RUN。
- 普通抓放来源与窗口由zyx-dc在#265提供，环境接受主机与构建记录，不要求镜像。

## 4. 待作者提供与已知限制

作者、单位、贡献、授权与论文/计划书/PPT的实际版本位置仍待确认。
当前只有论文侧材料与可复算记录；不宣称比赛材料已同步、论文已投稿或已发表。
