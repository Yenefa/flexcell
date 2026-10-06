# TB-002：预登记 T1 参数迁移仿真试点

2026-10-06，在学校 WSL 权威工作区完成了预登记的六个回合。FSM、Hybrid 各在
两个新初始布局完成 2/2，S1 源任务回测各完成 1/1。两臂均复用冻结的任务模板和
Skill，没有任务源代码适配。该结果只说明本次参数迁移及计账链路可运行。
**AC@90、独立资格评估、实体安全验收均 NOT_RUN，n≥50 继续冻结。**

## 设计与身份

- 起点：`d58f4f1d6854c6b74ab6c410dadd796cf991b592`，相同现有 Skill、对象、
  任务目标、Gazebo/MoveIt/控制器、coding assistance；固定 FSM 后 Hybrid 顺序。
- 目标：`transfer_t1_layout01_v1`，仅改变 A/B 的初始位姿，允许复用参数化 FSM。
  2 个适配种子 `2026100601/2026100602`，然后 1 次 `week1_demo_v1` 源任务回测。
  每臂固定三次，无替换失败；总共六次，没有再跑烟测或独立资格样本。
- 注册前扫描 345 份历史 episode、2,369 个双物体状态；目标布局与其中任何状态
  不在 1mm 内重合。这个可用历史上的新颖性不等于模型预训练未见或任务组合泛化。
- 完整的 [task manifest](plan/task_manifest.json)、[初态](plan/initial_states.json)、
  [历史摘要](plan/history_manifest.json)、[成功定义](plan/success_predicate.json)、
  [Skill 契约](plan/skill_contracts.json) 及两臂配置在运行前注册并封存。
- FSM fingerprint：`943071f0d0ef8ca4b48b876107d0bb18e2ccb3d67decfba28a1c87052cb2b2a6`。
- Hybrid fingerprint：`e43bd2f44acc828184ca49d0d326e9661d130cc2f00bac1176e68e5423902cae`。
  threshold 0.85；模型/权重/prompt/校准没有重新调整。
  calibration SHA：`34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`。
- 原有持久 ¥5 预算未清零，新增 ¥0.25 停止阈值在回合边界检查；阈值不是实际
  账单硬上限。最多每 cell 5 次的诊断限制未被用尽。

## 原始评分错误与独立修正

执行器 v1 要求 `final_state.outcome` 是整数 0，但真实 `EpisodeSchemaVersion=1`
由 TaskFSM 写出字符串 `"0"`。因此所有六条原始 summary/账本都误记 **FAILED**，
而各自 client JSON、goal UUID、实测双物体后置条件均明确成功。这是本轮评估器
错误，不能当作真实物理失败，也不能删除错误记录。

[原始账本](cost.jsonl)、每个 `attempt*/summary.json`、原始 episode/client、
首版 [执行过的源码](source/t1_pilot_executed_v1.py) 和首版测试全部保留。
`fsm/cost_report.json`、`hybrid/cost_report.json` 仍展示首版错误评分，供追溯。

独立的 [v2 修正报告](adjudication_v2/report.json) 标记为
**POSTHOC_SCHEMA_CORRECTION**，并由 [修正清单](adjudication_v2/correction_manifest.json)
绑定原账本及原始文件的 SHA256。它只修正 outcome 的表示类型，重新核对注册初态、
runtime identity、同一 run/goal UUID、客户端结果、成功的 PICK/PLACE/VERIFY、
两个有限非负且 ≤0.06m 的实测误差，以及 FSM replay/Hybrid 路由。
所有流程故障、未知终态、信号退出仍拒绝成功，尤其 `-6/134`；没有新 episode、
重新采样、改写原链或把首版和修正版成功率并池。修正发生在观察结果之后，
因此不把它当成预登记资格验收。

## 按身份与目的分开的诊断结果

| 臂 / 目的       | 回合结果 | Clef 接管 / DeepSeek | GPU 调用 / 实测总 tokens | policy.decide p50 / p95        |
| --------------- | -------- | -------------------- | ------------------------ | ------------------------------ |
| FSM 目标适配    | 2/2      | —                    | —                        | 0.014095 / 0.024146 ms，n=14   |
| FSM S1 回测     | 1/1      | —                    | —                        | 0.009130 / 0.036111 ms，n=7    |
| Hybrid 目标适配 | 2/2      | 12 / 1               | 13 / 18,616              | 2,962.163 / 5,646.242 ms，n=13 |
| Hybrid S1 回测  | 1/1      | 6 / 1                | 7 / 10,090               | 2,939.508 / 4,330.930 ms，n=7  |

这些是 `perf_counter_ns` 测量保留小数的完整 policy.decide 时延，包含升级调用；
排除了无世界快照的 bootstrap。p95 为 `(n-1)*q` 的线性插值。n 是决策数，
不是独立 episode 样本数，也不是 GPU 单次推理时延。全部 Hybrid 提案的模型、
权重和校准身份审计通过，未出现非 bootstrap 的 FSM fallback；FSM 三回合 replay 通过。
两个新布局和固定顺序不能证明任何一臂更可靠、更便宜或更省迁移工程工作。

| 成本维度                                               | 观测及缺失                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| 任务源代码 / 每臂仓内配置修改                          | 两臂均为 0；冻结 Skill 源码及实际安装源码检查相同                                  |
| 共同新增初始输入                                       | 2 个布局、4 个对象位姿、12 个数值分量，不能称为零配置输入                          |
| 编排 elapsed                                           | FSM 2.506664 分钟、Hybrid 3.507092 分钟；含策略切换/reset/仿真任务，非人的主动工时 |
| 人工活跃时间 / 等待时间                                | NOT_RUN；不推断为 0                                                                |
| 共同 harness 开发时间 / coding assistant tokens 和费用 | NOT_RUN；计账器没有这些数据                                                        |
| DeepSeek tokens                                        | 目标 1,505 input + 62 output；回测 1,511 + 62                                      |
| DeepSeek 新增预算上界                                  | 目标 ¥0.003506、回测 ¥0.003518，合计 ¥0.007024；实际账单 UNKNOWN                   |
| GPU tokens / 成本                                      | 总 tokens 28,706；输入/输出拆分、GPU 能源及所有权成本 UNKNOWN                      |

DeepSeek receipts 使用已有峰时无缓存预算费率；它不是实际计费。
[官方价格表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)区分峰时与缓存命中。
原始账本的 `known_amount_subtotal=0` 只表示没有已知金额，22 个请求金额均未知，
不能解读成免费。源任务回测单列，不加入目标迁移的成功率或费用。

## 保留的运行限制

Hybrid 的 [fleet.log](hybrid/fleet.log) 在启动时出现一次 Clef TCP `TimeoutError`。
随后三回合有真实、身份一致的 GPU 调用，不能抹掉该警告。
[收尾只读探测](validation/health_after_attempt01.json) 为 4/5 可达，第一条超时；
没有推理调用或新增机器人回合。网络抖动根因 **UNKNOWN**，本回执不宣称网络
稳定性验收。最终运行部署为 Hybrid 0.85；不改变 mirrored 网络、profile 或超时。

针对性测试为 **30 passed**，包含真实六份 episode 字符串终态回归、UUID 错配、
信号退出、缺失实测后置条件、保留 harness failure 和拒绝整数截断时延。
所有测试尝试与首次评分错误都保留在 `validation/`、`source/`，不当物理资格证据。

## 文件与复核

`fsm/`、`hybrid/` 下每个 attempt 保存 reset/pose/injection/client 命令 JSON、
完整 episode、各运行日志的原始追加片段、前后预算快照；Hybrid 还保存逐 API
主回执。驱动脚本、预检和测试在 `scripts/`、`validation/`。不包含凭据、权重或
build/install 产物。WSL 权威路径为 `/home/ros/agentic_workcell_ws`，账本路径沿用
运行时绝对路径；仓库镜像用相对文件摘要复核，不重写账本的路径/链。

```bash
cd /home/ros/agentic_workcell_ws
python3 setup/acceptance/transferbench_t1_20261006/scripts/verify_frozen.py
python3 -m unittest discover -s setup/transferbench -p 'test_*.py' -v
```

`SHA256SUMS.json` 封存确切文件集合及字节；它检测改动，不提供数字签名。
`adjudicate_t1.py --root 已完成回执 --out 新目录` 可只读复核，拒绝覆盖输出。
执行器 `run-arm` 对已开始的臂拒绝重跑；不要为了得到绿色首版账本而新跑这六回合。
