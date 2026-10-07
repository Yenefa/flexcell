# TB-RUN-002：不依赖家用 GPU 的 FSM 开发对照

2026-10-08，执行在 `/home/ros/agentic_workcell_ws`。
实现提交 `7c479e040211afe929484d2c94c2022ea20d126b`，分支为
`feat/transferbench-foundation-20261006`。44 项针对性测试、121 项全部离线仪器测试通过。
没有修改生产 Skill、物理参数、模型权重、校准或 `jev_backends.py`，没有重新构建安装树。

本机实际部署 FSM 0.85，指纹为
`fa0a1c6af0016f74741983d401d31ed170e5d8cdf6e52d823488b4f2ce596917`。
只读预检确认正在运行的策略确为 FSM，控制器、动作服务与 idle/released carry 正常；
GPU 健康项明确为 NOT_REQUIRED_FOR_FSM，tcp_reachable 和 route_eligible 为 null，
不伪造远端健康通过。Hybrid 的模型、校准与真实 TCP 检查保留。

冻结输入包仍为
`3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f`。
local-first 只重排同一组六个公开开发任务，总配额仍为十份原生 episode。
首次家用节点离线的零认领 STOPPED 记录保留，新计划固定其 plan/events 摘要。
第一次执行一段 T1 后真实 PAUSED；独立 driver 从已提交边界续跑 T3 和 S1，未重发 T1。

| FSM 任务      | 逻辑任务结果 | 新增原生 episode | 验收                                           |
| ------------- | ------------ | ---------------- | ---------------------------------------------- |
| T1 布局       | SUCCEEDED    | 1                | A/B 的 PICK、PLACE、VERIFY 及实测误差通过      |
| T3 三段交换   | SUCCEEDED    | 3                | 父任务、逐段新观察、组件回放和联合终态审计通过 |
| S1 旧任务回测 | SUCCEEDED    | 1                | 同一 FSM/Skill 与冻结源布局通过                |

三份逻辑任务全部成功，新增原生 episode 为五份。T3 的三段不是三个独立逻辑成功样本。
客户端全部 rc=0、action_status=4、outcome_val=0；没有将信号、失败或 timeout 当成功。
全部 episode 为 FSM，同一运行指纹，确定性回放通过。
原有 369 个 episode 字节不变，五份新 episode 完整保留；持久 ¥5 预算字节不变。
没有模型推理调用或新增预算 reservation；GPU 与实际 API 账单仍 UNKNOWN。
小样本成功没有解决 GRASP-B-001 的根因，也没有验收 NET-001。

最终只读健康检查通过，当前 fleet 保持 FSM。collector 为 PAUSED、completed_slots=3、
native_dispatch_quota_used=5，三个 Hybrid 槽位尚未认领，最多剩五份原生配额。
未来只有在代码、模型、校准和物理身份保持相同、实际 Hybrid 就绪后，才可继续同一账本。
源任务失败或未知/信号仍应终止，失败不能补采。

活跃 collector 已逐字节移到永久目录：
`/home/ros/fc_sync_logs/local_fsm_active_20261008/run`。
这个目录保存可续跑的日志和文件；本仓库只保存独立冻结快照，不在已封存回执里续写。
`snapshot/registered_plan.json`、`snapshot/registered_events.jsonl` 和 `execution/` 是
按用途拆开的同字节快照，不是 CLI 可执行的 run root。
历史 driver 中的原运行路径记录执行当时的位置，`validation/collector_handoff.json`
固定迁移前后的全部文件摘要与真实状态。

在 source 正确环境后，只读查看活跃 collector：

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/133_bounded_runner.py status \
  --root /home/ros/fc_sync_logs/local_fsm_active_20261008/run
```

`report.json` 区分本地前缀完成与完整六槽位未完成；原始延迟使用 perf_counter_ns 的
分数毫秒，仅作诊断。缺失或零值不可用于时延结论，不补写 0.0ms。
本次墙钟耗时不代表完整人工迁移成本。
`SHA256SUMS.json` 封存证据、输入、日志和源码快照。

**n≥50 与正式资格评估仍冻结，AC@90=NOT_RUN，ready_for_large_test=false。**
T1-001、T3-001 已作为开发场景接触，不能将这个旧公开候选包直接称为盲资格留出集。
未来准备新资格输入必须包含这五份新历史，独立保管、正式协议和预算仍待核定。

详见[执行器入口](../../../docs/BOUNDED_RUNNER.md)。
