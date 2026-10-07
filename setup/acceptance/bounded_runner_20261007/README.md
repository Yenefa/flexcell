# TB-RUN-001：执行器交付与零派发阻塞

2026-10-07，权威运行目录 `/home/ros/agentic_workcell_ws`。
执行器实现提交 `2e17ac9ad9af333fb1410ebdaf54258b97e58a3c` 已推送到
`feat/transferbench-foundation-20261006`；未合并 main。

六个开发槽位依次为 T1 FSM/Hybrid、T3 FSM/Hybrid、S1 FSM/Hybrid，
原生 episode 上限 10。冻结候选包摘要为
`3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f`。
实际完成离线 dry-run、独占登记与默认只读 run；默认 run 未修改日志。
29 项执行器针对性测试和 82 项既有离线仪器测试均通过，共 111 项。
这些测试不是机器人样本。

**真实执行未完成。** `--execute --max-slots 2` 在首个健康边界失败，
返回码 2，driver 随后返回码 1；全部日志和原始 STOPPED 事件保留。
日志只有 REGISTERED、STOPPED，没有 CLAIMED、COMMITTED 或原生任务。
新增 episode、模型调用和已消耗派发配额均为 0，已登记六个槽位均未运行。
真实暂停续跑、两臂任务结果与 decision latency 均为 NOT_RUN。

阻塞证据：首次 Clef TCP startup 探测在 10 秒截止后超时；独立诊断发现
GPU API 11435、SSH 22、RDP 3389 全部超时。22:45 北京时间的只读复核显示
本机 Tailscale 为 Running、self_online=true，而 `100.87.190.44` 的 Online=false，
最后在线时间为 20:22:49 北京时间；Tailscale ping 返回码 1。
这证明当次无法连接家用节点，离线的物理或软件原因仍 UNKNOWN。

本机 strict health 返回码 0、ok=true、hard_fail=[]、busy=false、task_state=IDLE，
carry_engaged=false。ROS_DOMAIN_ID=45、rmw_cyclonedds_cpp 和字面 IP 的 proxy bypass
均已确认。已有 episode 文件集合/字节和持久预算字节保持不变。
本轮没有重置世界、切换策略、修改代理/WSL 网络或推理重试。

下一次必须先恢复家用节点在线并通过新的只读就绪检查。原 `run/` 已终止，
不得覆盖或续跑；若旧日志仍为零认领、零派发，保留本回执并用新目录登记相同未运行槽位，
明确关联原 plan/events 摘要。这不允许替换已运行的失败样本或扩大十份原生配额。

`report.json` 记录当前阻塞和实测计数；`run/plan.json`、哈希链及原始健康输出
保留执行时的源码与输入身份；`source/` 是源码快照，`validation/` 保留测试和诊断。
`SHA256SUMS.json` 封存本回执全部文件。Git 不保存空目录；从 Git 恢复此零认领回执时，
只读状态查询前需重建空的 `run/attempts/` 目录，不能写入日志或派发任务。

**n≥50、正式资格评估继续 FROZEN，ready_for_large_test=false，AC@90=NOT_RUN。**
NET-001 未验收；B 抓取根因、GPU 与实际 API 费用保持 UNKNOWN。
独立留出集保管、正式协议和大批预算未核定，公开候选仍 PREPARED_NOT_RATIFIED。

详见[受限入口与规则](../../../docs/BOUNDED_RUNNER.md)。
