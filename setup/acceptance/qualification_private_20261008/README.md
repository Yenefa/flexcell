# TB-PREP-002：私有候选暂存与场景排除

2026-10-08，在 `/home/ros/agentic_workcell_ws` 离线执行。
实现提交 `4cdca5d878d473ad0e1ebdc4ad97b44eaa674c18`，分支为
`feat/transferbench-foundation-20261006`。
工具为 `setup/134_qualification_private.py` 及独立 wrapper，没有修改暂停执行器的冻结源码。

本机已另建 200 个候选布局：T1、T3 各 100；配对与回测共 450 个计划槽位。
全部 374 份可用历史 episode 纳入排除，包含本地 FSM 试点新增的五份；
旧公开候选包的全部 200 个布局另行排除，新布局与其在双物体 1mm 规则下重合数为零。
旧包和原失败回执均保留，没有按执行结果筛选或补采失败。

新种子、布局、输入清单和历史快照仅保存在权限 0700/0600 的本机私有目录：
`/home/ros/fc_sync_logs/qualification_private_20261008/inputs`。
本仓库只保存 commitment、CLI 回执、源码和验证证据，不包含新候选包。
`commitment.json` 的外部预期 SHA256 为：
`8d572dce24e7e3b5d97e2e3337842cda68055b133cc406da0a344475a311dd99`。
只有拥有私有包和相同源码/历史/校准/预算的本机可以完整复核。

| 实际检查             | 结果                                                         |
| -------------------- | ------------------------------------------------------------ |
| prepare / verify     | JSON `ok=true`，两次进程 rc=0                                |
| 重复 prepare         | JSON `ok=false`，rc=2，拒绝覆盖且原摘要不变                  |
| 针对性离线测试       | 22 passed，覆盖排除、路径、权限、身份漂移与重封篡改          |
| 权威目录全部离线测试 | 143 passed                                                   |
| 暂停账本             | 树摘要和冻结工具字节不变，仍 PAUSED / completed_slots=3      |
| 历史、校准、持久预算 | 字节摘要不变；没有新增 reservation                           |
| 原封存证据           | 46 文件的 STOPPED 回执与 153 文件的本地 FSM 回执全部复核通过 |
| 本轮执行量           | 原生 episode=0，模型调用=0，资格采样=0                       |

第一次全套测试在 Codex worktree 中为 142 passed / 1 failed：历史 T3 ledger 的证据
包含权威 workspace 绝对路径，在另一个路径下被绑定检查拒绝。
原失败日志保留，没有改 ledger、旧证据或该测试；回到权威目录后同组 143 项全过。
辅助证据采集脚本第一次因误读 `source_sha256` 键失败，原脚本保留；
`capture_before.py` 按真实 `executor_sha256` 只读补齐。两项都在 `validation/retained_failures.json` 登记。

`validation/before.json` 和 `after.json` 固定当前 collector、历史、预算与旧封存文件摘要。
活跃 collector 留在 `/home/ros/fc_sync_logs/local_fsm_active_20261008/run`，
三个未认领 Hybrid 开发槽位继续等待真实 GPU 就绪，旧本地前缀不重复执行。
网络最新状态见 `validation/gpu_status_readonly.json`，它没有调用模型。
`source/` 为实现提交逐字节快照，`SHA256SUMS.json` 封存此处的公开证据。

私有暂存的独立保管仍为 **NOT_ESTABLISHED**，状态 PREPARED_NOT_RATIFIED。
底层未修改的 schema-1 协议仍保留保守的 NOT_INDEPENDENT 旧模板；新包实际存储可见性
由 commitment 单独记录。不宣称盲留出集、IK/物理可达性或正式协议已验收。
NET-001=NOT_ACCEPTED、GRASP-B-001 根因 UNKNOWN、预算信封未核定、实际账单和 GPU 成本 UNKNOWN。
**n≥50=FROZEN、AC@90=NOT_RUN、ready_for_large_test=false。**

操作见[私有候选入口](../../../docs/PRIVATE_QUALIFICATION_INPUTS.md)。
