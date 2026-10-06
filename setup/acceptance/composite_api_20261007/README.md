# CORE-001：RunComposite 主线接口

2026-10-07 将 T3 的外层组合接入主线有类型的 `/run_composite` action。
唯一登记的 Hybrid 0.85 三段交换及唯一 S1 回测都成功，保留 **4 份原生 episode**。
目标阶段 **Clef 9 / DeepSeek 0**，回测 **6 / 1**；没有重复交换、补采或失败替换。
这是主线接口/控制流试点，n≥50、AC@90、实体安全和网络稳定性均未解冻。

## 接口与 ownership

`RunComposite` 接收显式 1..8 段计划，对象允许重复，stage_id 必须唯一。
全程持有与 RunDemo、RunPickPlace 相同的机械臂 admission 锁，其他任务无法插入段间。
每段复用原生 policy/Skill 执行器及独立 episode；开始前写入并 fsync STARTED，
原生 Verify 与新 Observe 均通过后才写 COMMITTED。最后另做一次联合 Observe。
取消、缺测、未知终态或失败都会阻止后续段；未知停止状态继续由既有隔离保护。

父回执是 `ACTUAL_COMPOSITE_TASK`，不能拼成一个假 EpisodeSchema 记录。
子段直接在父 action 里执行，并未单独向 DDS 发送 RunPickPlace goal。
`component_goal_uuids` 是内部执行关联 ID，子 episode 明确标记
`execution_kind=IN_PROCESS_COMPONENT`、`component_execution_id`、`parent_run_id` 和 stage_id。
真实 Skill/controller goal 仍由现有 action 传输确认。进程中断留下的 STARTED
不证明成功或停止，v1 不自动重放/续跑，须先确认 ownership 与实测状态。
[API 用法与边界](../../../docs/COMPOSITE_TASKS.md)。

## 冻结与单次执行

- baseline：`77e59e5e85769b5c5f0b5667b6e2e4028f57bc4a`。
- 运行前接口提交：`ac9ca84f9b0eacd234747d76b90e8ed44b435fe3`。
- 审计纠正提交：`d0197812c058c908793fc60369cbfa8c8a10c1fa`；运行时源文件没有再变。
- [前瞻计划](plan/manifest.json)、[输入](plan/input.json)、[完整部署](plan/deployment.json)
  和 [原生成功谓词](plan/success_predicate.json)均在运行前封存。
- fingerprint：`5dc07d3c0f5ce8b1cadd14549a9d7a238ff33de6871912e19e93c0796398fea9`。
  新旧指纹不并池；本轮只有 Hybrid API 试点，没有新 FSM 实测臂。
- 模型、prompt、calibration 未调优；calibration SHA 仍为
  `34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`。
  初态 A=(0.22,0,0.0175)、B=(0.20,-0.18,0.0175)，缓冲位=(0.12,-0.15,0.0175)。
- 调用一次组合 B→缓冲位、A→B原位、B→A原位；成功后仅执行已登记的一次 S1。
  单次 logical parent 与三个相关 component 分开，不相加充当独立样本。
  既有 ¥5 持久预算不清零，额外 ¥0.25 停止阈值仅在任务边界检查。

## 实际结果与原始失败

父 action 的 goal UUID 为 `1c153068f3884c8ea8c32a077cc45c04`，
run ID 为 `composite-ae09f5b4f0af4856`，status=4、typed outcome=0。
原生 components 依次为 `pick_place_v1-b5fdbecc`、`pick_place_v1-ba0f508e`、
`pick_place_v1-45eb1084`；S1 为 `week1_demo_v1-5a53f5b4`。
组合 7 份 fresh Observe 全通过，最终 A=(0.200282,-0.177524,0.017499)、
B=(0.222052,0.001248,0.017499)，缓冲位空置且 carry disengaged。
目标 18 个、S1 12 个 controller terminal 均为 status=4，无未知/隔离记录。
原生 client 命令均 rc=0；没有将 -6/134 解释为成功。

**原驾驶程序 rc=1 和首轮审计失败仍保留**：组合已经成功，但审计器错误地直接
比较父回执的原精度浮点与 EpisodeRecorder 已 round 到 9 位的小数。
差异仅位于 duration_s / final_position_error_m；比如首段误差为
0.00578832181526493 与 0.005788322。
[原失败输出](validation/pilot_attempt01.log)、[原审计器](validation/auditor_attempt01.py)
及 [失败登记](validation/audit_attempt01_failure.json)均未改写。

修正仅使用既有 EpisodeRecorder._sanitize 对齐序列化后做 equality；原精度有限、
非负、≤0.06m 判据保持不变。独立只读复核得到
[POSTHOC_SERIALIZATION_CORRECTION 报告](report.json)，不会把原 harness 错误或 rc
改成成功。随后通过 [source-only continuation](plan/continuation_source_only.json)
完成原计划中尚未执行的一次 S1，不重跑组合、不重置账本、不复用失败的目标样本。
v2/再次只读审计均保留；额外测试拒绝错误 UUID、缺失联合观察、NaN、bool 伪成功
以及原精度超阈值但 round 后等于阈值的错误。

## 路由、时延与成本

| 目的    | 原生 episode | Clef / DeepSeek 选择 | GPU 调用 / 总 tokens | policy.decide p50 / p95       |
| ------- | ------------ | -------------------- | -------------------- | ----------------------------- |
| 组合    | 3            | 9 / 0                | 9 / 12,563           | 2,639.679 / 4,227.423 ms，n=9 |
| S1 回测 | 1            | 6 / 1                | 7 / 10,127           | 1,918.911 / 2,439.732 ms，n=7 |

模型路由均为非 bootstrap、真实 tokens、fallback=false； bootstrap FSM 单列。
时延保留小数并携带 perf_counter_ns 时钟，排除 bootstrap，p95 线性插值，
属于完整 policy.decide（含升级），不当 GPU-only 延迟。
GPU 输入/输出拆分和成本未知。DeepSeek 回测有 1,511 input / 62 output，
既有预算账本按峰时无缓存费率记账上界 ¥0.003518，实际账单 **UNKNOWN**。
账本的已知金额小计 0 不表示零费用。

从 baseline 到纠正提交，源码/接口/CLI/审计/测试 **+840/-8 行**，配置 +28 行；
[Git 变更回执](validation/source_change.json)已记入 append-only ledger。
此前 T3 工具的复用和本次共享接口都属于工程投入。回执内 pilot 驱动、报告生成及
封存也有额外工程工作，未完整计量，不通过把它们排除于 Git LOC 就宣称零成本。
计时覆盖的部分 coding-agent wall elapsed 为 **7.687509 分钟**，含构建/测试/安装；
更早规划与初版代码、随后审计修正及交付未完整计量。S1 continuation 编排 elapsed
1.009482 分钟，含 reset/运行。人工活跃分钟、完整 agent 工时、assistant tokens/费用
仍 NOT_RUN；不填零、不宣称 Hybrid 工程成本胜出。

## 验证与复核

构建只选择 interfaces / skills 两包。完整 skills suite 最终 **300 passed**，其中
40 项新增纯合约/ROS bridge 测试覆盖并发锁、取消、未知 ownership、episode 缺失、
状态漂移和日志失败；记录器/只读审计 **42 passed**。这些是控制流/仪表验证，
不替代实体安全或 90% 可靠性证据。

运行时只更新 interfaces 和 skills，原包备份到
`~/.local/share/flexcell/mainline/composite_api_backup_20261007`。
首次接口复制遇到 3 个共有 environment hook 的 SameFileError，失败登记保留；
随后仅跳过可证同文件的 hook，验证 473 个生成接口文件和 35 个 Python 文件一致。
没有同步/删除整个 install 树。旧 source 快照和纠正后的 offline source 分别保留。
网络仍经 DERP；10s startup / 45s inference 配置保留，network_stability=NOT_ACCEPTED。

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/127_composite_audit.py \
  --receipt setup/acceptance/composite_api_20261007/execution/composite/parent.jsonl \
  --episodes setup/acceptance/composite_api_20261007/execution/composite/episodes \
  --deployment setup/acceptance/composite_api_20261007/plan/deployment.json
python3 setup/acceptance/composite_api_20261007/scripts/verify_frozen.py
```

原 driver 拒绝重复登记或执行，continuation 拒绝再次尝试 S1。
校验和封存确切文件集合；原始账本绝对路径不重写，镜像通过相对路径摘要校验。
