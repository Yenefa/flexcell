# 大批量测试前的开发检查点

2026-10-07：本轮声明范围的主线开发与有界功能验收完成，**正式资格评估和 n≥50 采样仍冻结**。
当前证据只能支持仿真接口、控制流与真实模型路由；不能称为 AC@90、实体安全、网络稳定性或通用迁移优势。

收尾已将 Gazebo world 的部署路径校正到 WSL 权威目录；两份 world 字节相同，
冷启后指纹不变、只读预检通过，新增原生 episode 为 0。
[路径校正证据](../setup/acceptance/authority_world_20261007/README.md)保留拥有的进程组和部署日志；
此前功能试点的封存文件保持原样。

后续已交付[批测候选输入准备](QUALIFICATION_PREPARATION.md)：可离线生成和复核冻结的
T1/T3 场景、FSM/Hybrid 配对顺序和旧任务回测清单。输出仍为 PREPARED_NOT_RATIFIED，
没有新原生 episode、模型调用或资格授权。

TB-RUN-001 的[受限执行器](BOUNDED_RUNNER.md)已接入既有任务链，
默认只读、显式执行六个开发槽位，上限 10 份原生 episode。
它支持已提交边界的暂停续跑和一次性槽位认领，正式资格采样仍冻结。
首次实际执行停在初始健康门：家用 GPU tailnet 节点离线、三端口超时；零认领、
零新增原生 episode，实际六槽位验收尚未完成。
[失败与网络诊断回执](../setup/acceptance/bounded_runner_20261007/README.md)完整保留原 STOPPED 日志。
后续入口支持 `--order local-first`：FSM 的 T1/T3/S1 可独立于家用 GPU 执行，
其只读健康门按实际已部署 FSM 策略核验。Hybrid 仍要求真实模型网络、身份和校准。
六槽位/十份原生配额不变，正式资格采样仍冻结。
2026-10-08 的[本地 FSM 实录](../setup/acceptance/local_fsm_20261008/README.md)已完成
T1、三段 T3、S1 三份逻辑任务，新增五份原生 episode，全部成功，真实暂停续跑通过。
模型调用和新增预算 reservation 为零；活跃 collector 停在三个未认领 Hybrid 槽位之前。
仓库保留独立封存快照，可续跑日志放在永久 `fc_sync_logs`；不在已封存证据里追加任务。
后续[私有候选暂存](PRIVATE_QUALIFICATION_INPUTS.md)排除已公开候选和新增历史，
新种子及布局留在 Git 工作树外，仓库只收录摘要；独立保管和正式协议仍未建立，n≥50 保持冻结。

## 已完成的入口

| 能力          | 结果与证据                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------------ |
| Clef 真实路由 | 校准有效，0.85 门通过；本轮目标 3 次由 Clef 接管，S1 为 Clef 6 / DeepSeek 1                      |
| 组合任务      | 1..8 段、共享机械臂 admission、逐段原生 episode、新观察及联合终态                                |
| 暂停与续跑    | 已有跨 fleet 重启试点；只继承已提交前缀，一次性 claim，重复及未知尾部拒绝                        |
| 整链声明预检  | 在任何 Observe/原生动作前检查后续占用和最终空置矛盾；新鲜测量及原生 IK/安全门仍必需              |
| 回执查询      | 只读区分 AVAILABLE / CONSUMED / NOT_PAUSED / UNKNOWN_TAIL / INVALID；查询不创建 claim 或驱动动作 |
| 审计边界      | 拒绝重复 JSON 键、非有限数和 `False == 0` 隐式等值；原始未舍入误差门槛不变                       |
| 批测前预检    | 核对部署指纹、38 个源码/安装文件、校准、实际策略/阈值、TCP、carry、控制器和旧封存文件            |

[本轮完整回执](../setup/acceptance/prebatch_ready_20261007/README.md)保留第一次验收脚本失败：
负向请求正确返回错误 60、ABORTED 状态 6、零动作；脚本误把 ABORTED 写成了 5。
只读纠正使用安装的 ROS 常量，原客户端 rc=2、driver 失败和账本 FAILED 标签均保留，
没有重发负向请求。只继续此前已登记且尚未运行的一段组合及一次 S1，共 2 份原生 episode。
18 个 controller 终态均为 4；没有未知传输或隔离事件。
345 项 skills 单元/回调测试和 54 项离线仪器测试通过，构建通过。这些测试计数不是机器人批次样本。

## 只读操作

所有 ROS 操作在权威工作区执行，source 不接管道：

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/130_composite_prepare.py plan \
  --plan setup/transferbench/composite_swap_v1.json
```

查询已存在的暂停回执需显式提供期望运行指纹：

```bash
python3 setup/130_composite_prepare.py checkpoint \
  --run-id composite-4de53ef286084c67 \
  --fingerprint b65aa2e2c0258d3ec705ee6cb4a4a6bb85f846dcdc987c556bb2ffde2188148f
```

该历史回执已消费，只能查询，不能再次续跑。AVAILABLE 只表示静态前缀核验通过；
实际提交仍需共享 arm admission 和新现场核验。查询及计划预检均返回 `dispatch_authorized=false`。

对一次明确的部署执行只读就绪检查，并保存独占输出：

```bash
python3 setup/131_prebatch_readiness.py --live \
  --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261007_132145/deployment.json \
  --receipt setup/acceptance/composite_api_20261007 \
  --receipt setup/acceptance/composite_resume_20261007 \
  --out /home/ros/fc_sync_logs/prebatch_readiness_review.json
```

示例部署路径属于本次检查点；实际使用时必须指定要核验的部署，不能拿旧 JSON 代替正在运行的版本。
输出文件已存在会拒绝覆盖。`--live` 只进行一次 TCP 探测、服务查询和 strict health，
不 reset、不调用推理或原生 task。即使 `read_only_preflight_ok=true`，
`ready_for_large_test`、`sampling_authorized` 仍为 false。成功 JSON 不能掩盖 -6/134 或其他信号。

WSL Git checkout 的旧 `head` 不是本次实现提交。代码身份由内容指纹及冻结源码证明；
本次实现为 feature 提交 `f10be54`，38 个安装源码逐字节一致。新旧指纹不并池。

## 下一阶段的审阅稿与限制

[资格评估 v2 草案](../setup/acceptance/prebatch_ready_20261007/plan/qualification_v2_draft.json)
提出 T1/T3 × FSM/Hybrid 共四个 cell、每 cell 固定 100 个逻辑任务、仅一个终点检查。
这只是统计方案。另有公开的候选布局包，但独立保管未建立，**没有盲留出集、没有实现或调用资格采样器、没有启动任何大批次**。
T3 测冻结三段交换的适配后可靠性，不宣称未见组合泛化；component episodes 不作为独立成功样本。

草案参考 [NIST 精确二项区间](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)，
为四个预先指定的 cell 使用 [Bonferroni 分配](https://www.itl.nist.gov/div898/handbook/prc/section4/prc463.htm)
的 alpha=0.0125。在独立二项假设成立时，100 次中至少 97 次成功才使提议的一侧精确下界达到 0.90；
该数值由只读草案生成器计算，不是已获得的实验结果。仍需审阅独立性与 reset、留出集保管、
配对 AB/BA 顺序、成功谓词、运行预算及源任务回测矩阵，再冻结正式协议。

| 仍未完成的资格门     | 当前结论与下一步                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| 独立留出集与正式协议 | 公开候选包 PREPARED_NOT_RATIFIED；独立保管未建立，历史适配和诊断 episode 不能改名成资格集         |
| NET-001              | 网络稳定性 NOT_ACCEPTED、直连根因 UNKNOWN；校园 mirrored / proxy 约束保持                         |
| GRASP-B-001          | B 抓取失败根因 UNKNOWN；本轮一次成功不能消除已保留失败，需独立诊断                                |
| 预算与成本           | 既有 ¥5 上限不重置；新增 ¥0.25 只是累积边界停止阈值。大批方案费用信封未核定，GPU/实际账单 UNKNOWN |
| AC@90                | 人工/助手完整适配成本未计量，仍 NOT_RUN；部分墙钟耗时不能补造人力投入                             |
| 平台及实体验证       | T2/T5 外部对象/平台、实体安全与运动中崩溃恢复均不属于本次验收                                     |

v1 成本记录器继续拒绝 qualification。此检查点不授权降低门槛、替换失败、合并不同校准/指纹、
修改冻结物理后端或开始 n≥50。正式大批测试的执行与授权属于下一阶段。
