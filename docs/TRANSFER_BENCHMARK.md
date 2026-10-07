# FlexCell TransferBench：迁移工程成本设计与 v1 记录器

状态：**设计与记录器已实现，T1 参数试点及 T3 三段交换试点已完成；AC@90、独立资格评估、实体安全验收均为 NOT_RUN。**
资料核验日期：2026-10-06。首个目标是前瞻性地记录一次受控迁移需要的工程工作，
不是把历史运行成功率重新命名为迁移能力。离线账本本身不执行机器人任务；
T1 执行器复用本机现有 ROS/Gazebo 部署，不安装外部仿真栈。

主线现已补齐整链无动作预检、暂停回执只读查询和统一批测前就绪报告。
[开发检查点](PRE_BATCH_CHECKPOINT.md)与[本轮回执](../setup/acceptance/prebatch_ready_20261007/README.md)
记录 2 份原生功能回归及一次零动作拒绝。负向任务保持 FAILED 标签，首轮状态常量
错误的 harness 失败只读纠正后保留；不计作资格样本，也不重发请求。
资格 v2 已另补[离线候选输入准备](QUALIFICATION_PREPARATION.md)：固定 T1/T3 清单、配对顺序、
旧任务回测、源码及校准身份，可独占生成并严格复核。候选包公开且待核定，不称盲留出集；
统计方案仍为不可执行审阅草案，v1 qualification、AC@90 与 n≥50 继续冻结。

## 官方 benchmark 能借鉴什么

| 来源                                                                                                              | 核验结果                                                                                                                                                             | 对 FlexCell 的设计启发                                                                          |
| ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [Meta-World 官方定义](https://metaworld.farama.org/benchmark/benchmark_descriptions/)                             | ML1 在同一任务中用 50 个训练位置、10 个留出位置；ML10 为 10 个训练任务、5 个测试任务，ML45 为 45/5。MT50 使用全部 50 个训练任务，不能当作留出任务泛化。              | 原子 Skill 的位置变化和新任务变化分开；借鉴其受控划分，不声称现有 ROS Skill 已通过 Meta-World。 |
| [LIBERO 原论文](https://arxiv.org/html/2306.03310)与[官方代码](https://github.com/Lifelong-Robot-Learning/LIBERO) | Spatial/Object/Goal 各 10，加 LIBERO-100，共 130；100 拆成 90 个预训练任务和 10 个长程下游任务（代码名 `libero_10`）。FWT 是训练检查点上的成功率平均；不是工程分钟。 | 一次改变一个迁移轴，预先指定顺序，逐阶段回测旧任务。平台迁移是 FlexCell 自己增加的轴。          |
| [RoboCasa foundation-model 评估](https://robocasa.ai/docs/build/html/benchmarking/foundation_model_learning.html) | 目标评估有 Atomic-Seen 18、Composite-Seen 16、Composite-Unseen 16。Composite-Unseen 相对预训练未见；官方同时有目标任务 fine-tuning 设置，不能一概称为零样本。        | 已见组合、未见组合、是否允许目标任务适配分别登记。                                              |
| [RoboCasa lifelong 评估](https://robocasa.ai/docs/build/html/benchmarking/lifelong_learning.html)                 | 65 个原子任务起步，再逐阶段引入 2–3、4–5、6+ stage 任务；每阶段回测之前所有阶段。                                                                                    | 增加组合长度时保留旧任务成功矩阵，不能只展示新任务。                                            |

本轮审阅的这些评估没有把人工迁移工程成本作为核心指标。这个结论的范围仅限
上述资料；不能据此声称全领域没有类似指标，或 FlexCell 是首个提出者。

[NVIDIA Agent Skills](https://github.com/nvidia/skills) 是供 coding agent 使用的
软件工作流指导；FlexCell 的 Observe/Pick/Place/Verify 是运行时 ROS action 能力。
它们处在不同接口。当前方案借鉴能力封装方法，不引入 Isaac ROS 或改变 Jazzy 部署。
[RLBench 官方仓库](https://github.com/stepjam/RLBench)的换臂接口可供未来平台轴研究，
本轮未接入，也不将它的结果迁用到 OpenMANIPULATOR-X。

## 分层与迁移轴

下面是 FlexCell 自己的测量层次，不是外部 benchmark 的官方分层。

| 层次        | 测什么                                          | FlexCell 当前落点                                             |
| ----------- | ----------------------------------------------- | ------------------------------------------------------------- |
| L0 执行基础 | 发现、时间、controller goal、carry、规划可用性  | 控制器隔离与本机 DDS/校时证据；先区分基础设施失败和任务失败。 |
| L1 Skill    | 固定 Skill 在受控参数变化下的契约、后置条件     | Observe/Pick/Place/Verify/MoveToPose；空间、对象轴分别报告。  |
| L2 组合     | 固定 Skill 库上的新依赖关系、目标组合和恢复逻辑 | 使用 DecisionPolicy → Task Executor → Skill action 接口。     |
| L3 迁移成本 | 从冻结起点到新任务可用的人工、修改量与调试投入  | 新的前瞻账本；旧 episode 不提供此前的人工计时。               |

| 轴      | 只改变什么                         | 固定什么                                        |
| ------- | ---------------------------------- | ----------------------------------------------- |
| T1 参数 | 初始布局、目标位姿等数值参数       | 对象语义、任务模板、Skill 实现、平台            |
| T2 对象 | 对象类别或已声明几何属性           | 布局规则、任务目标、Skill 契约、平台            |
| T3 组合 | 之前未覆盖的任务依赖关系或成功谓词 | 原子 Skill 实现、对象、平台                     |
| T4 恢复 | 预先登记的新故障条件与恢复要求     | 正常任务、故障注入实现、恢复预算                |
| T5 平台 | 机械臂或执行后端                   | 上层 Skill 契约、任务及成功谓词；适配器工作另记 |

S1 已经运行 Observe→Pick→Place→Verify，原有 S2/S3/S5 已含恢复条件；这些不是
新组合或新恢复能力。`GoalPlan.assignments` 已支持任务腿顺序；单纯换 A/B 顺序
可能只是参数变化，不能自动归 T3。现有 S7 也有扰动，因此首个 T1 必须选独立
留出布局，不把已调过的 S7 再当未见任务。无法隔离的多轴变化单列，不并池。

## 首个试点：T1 留出布局，先登记再适配

`setup/transferbench/pilot_draft_v1.json` 保留为历史 **DRAFT_PLAN**，锚定 `dcff1df`。
2026-10-06 的实际试点另从 `d58f4f1` 起点注册了 **PROSPECTIVE_PLAN**：
两个预登记布局，每臂 2 次目标任务、1 次 S1 源任务回测，固定 FSM 后 Hybrid。
完整注册文件和原始运行在
[T1 回执](../setup/acceptance/transferbench_t1_20261006/README.md)。

布局只保证未与登记前可用的 345 份 episode 中任一双物体状态在 1mm 内重合，
不宣称模型预训练未见或广义 OOD。未生成独立资格评估留出集；这些是适配阶段
诊断状态，不能再作为盲测验收集。

转成 `PROSPECTIVE_PLAN` 前必须封存以下文件，`init` 将原始路径转换为内容 SHA256：

- `task_manifest`：迁移轴、源任务、目标任务、适配/留出种子、允许修改范围、任务顺序、
  成功谓词版本、每 cell 调试上限 5、工程时间/API 预算、旧任务回测清单。
- `initial_states`：两臂使用同一初态清单；对象/目标在原工作空间内，非接触物理改造。
- `success_predicate`、`skill_contracts`：固定验证器与完整 Skill 实现/契约的内容摘要。
- `baseline_config/fsm`、`baseline_config/hybrid`：分别冻结配置、prompt、模型/校准身份、
  runtime fingerprint、允许的 coding assistant 与费用预算。

该试点的 FSM、Hybrid 都完成目标 2/2、回测 1/1，按 arm/purpose/fingerprint/
calibration 分 cell。两臂均复用现有参数化 FSM/Skill，任务源代码与每臂仓内配置
没有修改；共同新增的输入是 2 个布局、4 个对象位姿、12 个数值分量。
它检验了“登记→运行→计账→回测”的链路，未证明 Hybrid 比 FSM 少用工程工作。

执行器首版错误地要求 episode 的终态 outcome 为整数，而真实 schema 写成
字符串 `"0"`，导致六条原始账目误记 FAILED。原账本、summary、日志和执行过的
源码全部保留；独立的 `adjudicate_t1.py` 仅修正该表示差异，核对同一 run/goal UUID、
初态、指纹、路由与双方实测后置条件，输出明确标记 **POSTHOC_SCHEMA_CORRECTION**
的 v2 报告。没有新 episode、替换失败或改写原始 hash chain。

Hybrid 目标 cell 为 Clef 12 次、DeepSeek 1 次，回测为 6/1；20 次 GPU 调用共
28,706 个实测总 tokens，输入/输出拆分未知。DeepSeek 两次的峰时无缓存预算上界
合计 ¥0.007024，实际账单和 GPU 成本未知。人工分钟、共同 harness 开发成本和
coding assistant 的 tokens/费用没有计量；账本只记录两臂运行编排 elapsed
2.507/3.507 分钟，含切换、reset 和机器人执行，不能解释为人的主动工程时间。
预算沿用已有 ¥5 绝对上限，新增 ¥0.25 停止阈值仅在回合边界检查，不是账单硬上限。
[DeepSeek 官方价格表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)支持预算
上界所用峰时费率；缺少缓存命中明细，不能据此填实际费用。

启动日志保留一次 Clef TCP 探测超时，收尾只读探测 4/5 可达；三回合真实推理
审计通过并不消除网络稳定性问题，超时根因 UNKNOWN。继续扩大采样前应另行处理。
不改变当前校准、模型、prompt 或部署超时。

公平比较允许 FSM 复用参数化任务模板、配置表和现有 Skill；不能强迫它为每个
新布局新增状态。两臂都可在预定范围内适配，所有适配和校准投入都计费。人工顺序、
coding assistant 使用和操作者经验也要登记；单人试点只能检验记录链路，不能
排除操作者先学会任务后另一臂受益的顺序效应。

独立评估不能反馈给适配人员后继续作为同一份留出集。每阶段回测旧任务，按
“适配阶段 × 被测任务”记录成功率及退化；每个预定顺序独立报告。不同 runtime
fingerprint、校准身份、protocol 或评估目的分 cell；一次迁移可以产生多个指纹，
但不能把这些运行的成功率合成一个验收率。

## 成本与达标规则

T3 随后接入主线有类型的 RunComposite 接口，支持显式 1..8 段计划、全程机械臂锁、
重复对象、逐段原生 episode 与 fresh Observe。2026-10-07 单臂功能试点完成一次
Hybrid 组合及一次 S1，共 4 原生 episode；目标 Clef 9 / DeepSeek 0，回测 6 / 1。
它属于 API/控制流证据，不是追加的双臂迁移成本比较或泛化验收。
[接口与中断边界](COMPOSITE_TASKS.md)、
[保留首轮审计失败的主线回执](../setup/acceptance/composite_api_20261007/README.md)。
审计对齐既有 episode 浮点序列化后只读复核，没有重跑组合；原 driver rc=1 保留。
组件 UUID 标为进程内执行关联，不充当另一个被 DDS 接受的原生 task goal。

T3 已另行预登记并运行“B→缓冲位，A→B原位，B→A原位”，每臂一次组合和一次
S1 回测，各 1/1，共 8 份原生 episode。B 被二次访问，并增加最终联合位置/缓冲
空置谓词，不能由现有两个唯一对象的 assignment 换序表示。两臂共用固定外层
编排，Hybrid 的模型只路由段内动作；目标 9 次均由 Clef 接管，S1 为 Clef 6 次、
DeepSeek 1 次。没有模型/prompt/校准调优，没有新增样本替换失败。
[完整 T3 定义、父子任务证据与计账](../setup/acceptance/transferbench_t3_20261006/README.md)。

共享执行器登记前新增 352 行、测试 59 行，之后还增加报告器和实录测试；这是
工程投入，不能算零代码。9.207 分钟仅为部分共享开发 elapsed（含交付开销），
先前规划、网络修正、随后报告/封存及人工活跃时间未完整计量。单次组合成功不能
证明通用组合泛化或 Hybrid 工程成本优势。父级逻辑任务和相关原生 component
episodes 分开，不能相加充当独立样本；S1 回测费用也不混入目标阶段。

学校启动 TCP 截止时间现在可由部署明确配置，选 10 秒并受推理 45 秒上限约束。
新 helper 不改冻结 prompt 字节，旧校准有效；新 runtime 指纹另报。
[NET-001 的 2 秒失败和 10 秒成功对照](../setup/acceptance/startup_health_20261006/README.md)
保留完整限制：链路仍走 DERP(tok)，直连根因 UNKNOWN，网络稳定性未验收。

成本是一个向量，不将美元、分钟、LOC 用任意权重拼成总分：

- 人工活跃分钟：主动适配时 `start --actor human`，等待前 `stop`；v1 是单操作者计时。
- coding agent elapsed minutes、等待分钟：分别使用 `coding_agent`、`wait`，不并入人工分钟。
  本轮工具开发时间也不是未来 T1 适配时间；历史 commit 时间不能补造人工用时。
  `wait` 指该操作者纯等待，必须先关闭 human session；工具计量声明的区间，不自动
  判断人的注意力或离席，活动分类仍需操作者准确记录。
- API：逐 request 记录 scope、真实输入/输出 tokens、费用和币种，包括失败、校准和
  未得到有效决策的调用。未知费用用 `null`，报告已知小计与未知请求数；不当作零费用。
- 修改量：从各臂冻结 base 到当前 head 的 code/config added/deleted，以及审阅确认的
  新增规则/状态数；生成的证据、权重、build/install 不计入工程 LOC。只展示最新
  baseline-to-head snapshot，不把多个累计 diff 相加。未知规则/状态数用 `null`。
- 机器人/仿真调试 trials：失败、harness error、UNKNOWN 全保留；实际 trial 用原始
  run ID，reset 等无 episode 的失败也分配独立 attempt ID。校准/训练样本数另随原始
  API/采样 receipt 保存，v1 尚未自动汇总样本数。每个 trial/API 只引用一个独立主回执，
  共同配置放在 plan 中，避免同一 episode 换文件名或 event ID 后重复计数。

`AC@90` 拟定义为首次在**预先指定的独立评估检查点**达到成功率标准时，累计投入的
成本向量；`Time-to-Threshold` 单独报告人工分钟。未来必须先登记固定 n、成功判据、
置信方法和预算；多个达标检查点还需处理重复检验，不能不断试跑直到有一批全绿。
预算耗尽未达标应报告未达标/删失，不填零，也不删除失败。

v1 的 qualification 全部 **FROZEN**，CLI 拒绝 qualification trial 和启用该门，
AC@90 永远报告 **NOT_RUN**。`n≥50` 大批次继续冻结；记录器也不负责执行采样。
5/5 的双侧 Wilson 95% 下界约 0.566，不能证明可靠性达到 90%。现有线上 S1 5/5
只作为运行基础证据，不能重标为 T1 留出验收或推算 FSM/Hybrid 的人工成本。

诊断报告同时展示 `retained_attempts`、完整 outcome 计数、`completed_denominator`；
HARNESS_ERROR/UNKNOWN 不放进已完成任务比例，但缺失情况必须同时显示。
`return_code=-6/134` 即使较早 JSON 写成功，也按 ABORTED_PROCESS 保留；其他退出码
不取代 JSON 任务 outcome 的判定。记录器只核验引用证据的内容完整性，不自动解析
episode 或证明人工填入的 outcome/费用真实；字段明确叫 `reported_outcome`。
物理安全、模型 replay 和决策时延由相应工具验收；本工具不填假的 0.0ms 或安全 PASS。

## 离线记录器用法

`setup/125_transfer_cost.py` 只用 Python 标准库。账本独占创建、锁内追加、每行包含
上一行摘要，读取时检查所有行及引用文件的 SHA256。它检测误改，**不是签名或不可
伪造的证明**；完成的 receipt 还需按项目惯例封存。保留未知终态与损坏尾行，工具
拒绝继续而不自动截断修复。引用 appendable 运行日志前，应先复制成不可变快照。

以下只创建草案账本；开始实际适配前应换成已封存的 `PROSPECTIVE_PLAN`：

```bash
cd /home/ros/agentic_workcell_ws
mkdir -p /home/ros/fc_sync_logs/transferbench_t1_layout01
python3 setup/125_transfer_cost.py init \
  --spec setup/transferbench/pilot_draft_v1.json \
  --ledger /home/ros/fc_sync_logs/transferbench_t1_layout01/cost.jsonl
```

在人工真正开始适配时计时；暂停、等待或活动切换时结束 session，并引用工作产物：

```bash
python3 setup/125_transfer_cost.py start \
  --ledger /home/ros/fc_sync_logs/transferbench_t1_layout01/cost.jsonl \
  --arm hybrid --actor human --session layout01-config --activity configure-layout
python3 setup/125_transfer_cost.py stop \
  --ledger /home/ros/fc_sync_logs/transferbench_t1_layout01/cost.jsonl \
  --session layout01-config \
  --evidence /home/ros/fc_sync_logs/transferbench_t1_layout01/config-diff.txt
```

时长由同一 Linux boot 的 `perf_counter_ns` 算出，不受墙钟跳变影响。跨 WSL 重启
结束 session 会拒绝，不推算缺失时长；原 session 保留为 open，不记零分钟。
可用 `close-unknown --session ID --reason 原因 --evidence FILE --ledger FILE` 追加未知
时长的关闭记录，再开始新 session；原记录不删除，`effort_status` 保持 INCOMPLETE。
`effort_minutes` 仅为已测区间小计，不能把存在未知区间的数字当成完整工程时间。
开始时间在取得账本锁并完成历史证据校验之后采样，结束时间在读取/校验账本之前
采样，排除工具内部等待。报告另列按 arm/purpose 的累计尝试数，避免拆 case 或
fingerprint 隐藏总量；达到 50 会提示需要审阅。它不识别外部批次边界，也不授权采样。

`record --event FILE.json` 接受三种 receipt：`trial`、`api`、`change_snapshot`。
字段定义见脚本 `validate_event`；`evidence` 在输入 receipt 中是文件路径列表，
落入账本后是绝对路径及 SHA256。trial 的 `purpose` 只接受 `adaptation/regression`。
下面是需填真实身份和证据路径的 trial 模板，不能原样执行：

```json
{
  "event_id": "trial-actual-run-id",
  "kind": "trial",
  "arm": "hybrid",
  "trial_id": "actual-run-id",
  "purpose": "adaptation",
  "case_id": "T1-layout-01",
  "runtime_fingerprint": "填原始 episode 的64位指纹",
  "calibration_sha256": "填原始运行的64位校准摘要；无校准用null",
  "reported_outcome": "FAILED",
  "return_code": 0,
  "evidence": [
    "/home/ros/fc_sync_logs/transferbench_t1_layout01/actual-episode.json"
  ]
}
```

```bash
python3 setup/125_transfer_cost.py record \
  --ledger /home/ros/fc_sync_logs/transferbench_t1_layout01/cost.jsonl \
  --event /home/ros/fc_sync_logs/transferbench_t1_layout01/trial-receipt.json
python3 setup/125_transfer_cost.py report \
  --ledger /home/ros/fc_sync_logs/transferbench_t1_layout01/cost.jsonl \
  --out /home/ros/fc_sync_logs/transferbench_t1_layout01/report-01.json
```

账本和 report 均拒绝覆盖；再次报告使用新文件名。未记录的分钟显示 `null`，不是零。
重复 trial/request ID、复用 trial 证据、负时长、bool 当数字、非有限数、身份字段格式
错误、修改量 base 错配会被拒绝。原始失败文件始终保留。

针对性离线验证：

```bash
python3 -m unittest discover -s setup/transferbench -p 'test_*.py' -v
```

本轮封存的测试输出和合成 fixture 见
[transferbench_foundation_20261006](../setup/acceptance/transferbench_foundation_20261006/README.md)。
fixture 的 record kind 为 SYNTHETIC_TOOL_FIXTURE，不能当机器人、迁移或付费调用证据。
