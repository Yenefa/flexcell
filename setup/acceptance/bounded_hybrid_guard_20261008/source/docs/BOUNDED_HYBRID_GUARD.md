# 三个 Hybrid 槽位的快臂来源门

TB-RUN-003 延续 RFC #15 的有界开发验收。`setup/135_bounded_hybrid_resume.py` 为已经完成
FSM T1/T3/S1、暂停在第三个槽位后的 collector 增加一个独立 guard。它复用既有 runner 的锁、
一次性 claim、终态提交、健康检查、原生配额及持久预算；当前生产 Skill、模型、校准和物理身份不变。
总配额仍是六份逻辑任务、十份原生 episode，最多剩三个 Hybrid 槽位、五份原生 episode。
新入口不能启动 n≥50 或正式资格采样。

旧路由审计允许快臂提案全部 skipped 或缺失、只有慢臂决策的 episode 通过。
这个 guard 在原生任务返回后、runner 提交终态之前，从原始 episode 重算来源：

- 每个有模型决策的 episode 必须出现真实快臂提案，token 必须是正整数；bootstrap 不计模型分母。
- 每份 Hybrid 逻辑任务必须有正的快臂调用数及实测 token，T3 各组件分别检查。
- runtime fingerprint、threshold、模型与校准身份必须一致，拒绝非 bootstrap FSM fallback。
- 客户端信号、未知终态或非零退出不能借成功 JSON 通过。

允许快臂真实调用后全部升级到慢臂，不要求 fast selection。
`fast_calls` 和 `fast_tokens` 是日志中的观测证据；这里没有联网重放，也不声称能验证伪造日志。

## 终态和身份

每份新 attempt 保存 `base_backend_result.json` 和 `fast_arm_gate.json`，最终 `result.json`
绑定 guard 摘要。旧适配器返回 SUCCEEDED、来源门失败时，提交 HARNESS_ERROR 并 STOPPED，
下一个槽位不执行。原本的 FAILED/UNKNOWN 仍保留，并在门失败时停止；不替换或补采失败。
来源门通过的已知目标失败可以按既有规则继续，源任务回测失败仍停止。
原始结果始终保存，不能把 harness error 计入物理成功率。

guard 是新增的开发仪器身份，清单固定其源码和已提交 FSM 前缀；旧 plan/events 不被改写。
新 attempt 的 gate 和原始证据都纳入原 collector 的封存文件。
续跑时重算已提交 gate，拒绝先用旧入口执行、再把结果归到本 guard 的做法。
新旧仪器结果不能并池作为资格证据。默认查询不创建 runner 锁、不写 collector、不调用模型。

远端 `fix/hybrid-batch-provenance` 的 `c79e0c6` 提供生产 routing audit / batch runner 修复。
此处只读参考其来源门规则，没有修改该并行分支，也没有将它混入当前暂停的生产身份。
该生产修复落地后，仍需新 runtime fingerprint 下的在线验收，历史失败保留。

## 本机入口

在 WSL 权威目录登记；guard 文件必须在 collector 外，不能覆盖已有文件。
`--revision` 使用包含新入口的 Windows feature 完整提交 SHA。

```bash
cd /home/ros/agentic_workcell_ws
python3 setup/135_bounded_hybrid_resume.py register \
  --root /home/ros/fc_sync_logs/local_fsm_active_20261008/run \
  --out /home/ros/fc_sync_logs/local_fsm_active_20261008/hybrid_resume_guard.json \
  --revision <完整feature实现提交SHA>
```

保存返回的 `guard_sha256` 作为外部预期值。先做默认只读检查：

```bash
python3 setup/135_bounded_hybrid_resume.py run \
  --guard /home/ros/fc_sync_logs/local_fsm_active_20261008/hybrid_resume_guard.json \
  --expected-sha256 <登记返回的guard_sha256>
```

`guard_verified=true` 只表示来源门、冻结源码与前缀匹配；不表示 GPU 在线或允许大批次。
只有真实 GPU 网络、模型及现场依赖均就绪后才显式执行，source 不接管道：

```bash
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/135_bounded_hybrid_resume.py run \
  --guard /home/ros/fc_sync_logs/local_fsm_active_20261008/hybrid_resume_guard.json \
  --expected-sha256 <登记返回的guard_sha256> \
  --execute --max-slots 1
```

默认最多执行一个 Hybrid 逻辑任务，在已提交边界暂停；后续使用同一 guard 继续未认领槽位，
`--max-slots` 只能为 1..3。被 STOPPED、COMPLETE 或 UNKNOWN_TAIL 的 collector 不可续跑。
不要在 GPU 离线时显式执行：既有依赖门失败会留下 STOPPED 记录，不会自动恢复原暂停状态。
持久 ¥5 预算和新增 ¥0.25 累积边界阈值保留，费用信封及实际 API/GPU 成本仍未核定。

NET-001 与 GRASP-B-001 尚未解决，独立保管和正式协议尚未建立；
`qualification_sampling_authorized=false`、`ready_for_large_test=false`、`n_ge_50=FROZEN`。
