# TB-RUN-003：固定暂停前缀的 Hybrid 续跑来源门

2026-10-08，在 `/home/ros/agentic_workcell_ws` 完成离线实现、登记和查询。
实现提交 `f2f3ff11d70fea8b7d8ad77dd245698d04d7a6a2`，分支为
`feat/transferbench-foundation-20261006`。31 项针对性测试、174 项全部离线仪器测试通过。
没有修改生产 Skill、原执行器冻结源码、物理参数、模型、校准或安装树，没有新增原生 episode。

新入口 `setup/135_bounded_hybrid_resume.py` 在原 runner 提交每份 Hybrid 逻辑任务终态前，
从原始 episode 重算每个组件的真实快臂调用及 token。仅慢臂的原绿色结果变为
HARNESS_ERROR，collector 停止，不派发后续槽位。
快臂真实调用后全部升级到慢臂仍可通过，不要求 fast selection。
T3 来源门在整个逻辑任务返回后执行，发现异常时其已完成组件保持原样，不撤回或补采。

原始适配器结果、来源门回执和最终结果分别保存；已有 FAILED/UNKNOWN 保留。
守门是新增的开发仪器身份，不能和未守门结果并池作资格证据。
它复用原 collector 的单个 runner 锁、一次性认领、配额、健康和预算门，没有改写既有 FSM 前缀。
默认 run 只读；仅显式 `--execute` 可以使用剩余三个已登记 Hybrid 槽位。

| 本机实际检查                       | 结果                                                                  |
| ---------------------------------- | --------------------------------------------------------------------- |
| guard register / status / 默认 run | 三次 JSON `ok=true`，rc=0，零动作、零模型调用                         |
| 重复登记                           | JSON `ok=false`，rc=2，拒绝覆盖且原摘要保持不变                       |
| collector                          | PAUSED，completed_slots=3，native_episode_count=5，三个 Hybrid 未认领 |
| 冻结前缀及执行器                   | 树摘要与原 executor 源码固定值不变                                    |
| episode 历史 / 预算 / 校准         | 374 份历史及持久文件字节不变，无新增 reservation                      |
| 私有候选包                         | 原 commitment 外部摘要下复核仍通过，没有公开新布局或种子              |
| 旧封存文件                         | STOPPED 46 文件、本地 FSM 153 文件、私有准备 30 文件全部复核通过      |
| 本轮新增执行量                     | 原生 episode=0，模型调用=0，资格采样=0                                |

31 项针对性测试使用合成适配器，验证零快臂提案停止、T3 组件分别检查、纯慢臂选择但真实
快臂调用允许、无效 token 和身份拒绝、信号/退出拒绝、失败保留、暂停续跑与绕过检测。
这些测试的 native IDs、token 数和调用是 fixture，不能作为真实机器人或模型执行证据。
本机实际 guard 登记与默认 CLI 检查独立保存在 `validation/`。

活跃 guard：
`/home/ros/fc_sync_logs/local_fsm_active_20261008/hybrid_resume_guard.json`。
其外部预期 SHA256 为：
`0f8c9ea79dec8686c37c0d465b4cc70692c28b99f2c3235f8cb53f63429f5179`。
`guard_manifest.json` 是相同字节的审阅副本；原 collector 留在同目录的 `run/`，没有迁移或覆盖。

可以直接运行当前只读入口：

```bash
cd /home/ros/agentic_workcell_ws
python3 setup/135_bounded_hybrid_resume.py run \
  --guard /home/ros/fc_sync_logs/local_fsm_active_20261008/hybrid_resume_guard.json \
  --expected-sha256 0f8c9ea79dec8686c37c0d465b4cc70692c28b99f2c3235f8cb53f63429f5179
```

最新网络只读查询显示家用 GPU 仍离线，见 `validation/gpu_status_readonly.json`。
因此本轮实际 guarded Hybrid execution 为 **NOT_RUN**，没有使用 `--execute`。
GPU 与现场依赖就绪后按[续跑入口](../../../docs/BOUNDED_HYBRID_GUARD.md)执行同一 guard，
默认一次一份逻辑任务，在已提交边界暂停；不得重发旧 FSM 任务。

`source/` 是实现提交的逐字节快照，`validation/before.json` 和 `after.json` 固定原状态。
`SHA256SUMS.json` 封存本次代码、登记回执及日志；封存后不继续向这里追加任务。
guard 源码或生产身份变化会拒绝继续，远端生产来源门修复仍需新指纹的独立在线验收。

NET-001=NOT_ACCEPTED、GRASP-B-001 根因 UNKNOWN、独立保管及正式协议/预算未核定。
**n≥50=FROZEN、AC@90=NOT_RUN、ready_for_large_test=false。**
