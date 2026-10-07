# 受限执行器与开发验收

TB-RUN-001 延续 [RFC #15](https://github.com/Yenefa/flexcell/issues/15)。
`setup/133_bounded_runner.py` 接入冻结输入与既有 ROS 任务链：T1 使用 RunDemo，
T3 使用 RunComposite，S1 回测同一冻结 Skill/Policy。正式 n≥50 资格采样仍冻结。

默认 dry-run 复核完整 450 槽位清单，只提取两臂各一个 T1、一个 T3、一次 S1。
六个开发槽位的原生 episode 上限为 10，不能通过参数改成 50。
开发请求的 scenario_id 明确加 `development_` 前缀；几何和任务链保持冻结候选定义。
register 保存输入副本、源码身份、已有预算与历史摘要；生成目录已有即拒绝覆盖。

`--order local-first` 将相同六个开发任务排序为 FSM 的 T1/T3/S1，再到 Hybrid 的 T1/T3/S1。
任务、几何和十份总配额不变；这是开发排序，不修改冻结的正式候选清单或配对顺序。
已部署 FSM 的只读预检检查实际 ROS 策略、控制器与 carry，模型健康标记为
NOT_REQUIRED_FOR_FSM；Hybrid 的校准、身份与真实 TCP 门保留，并在认领下一槽位前复核。
FSM 不能用当前 Hybrid 的成功健康报告冒充激活；实际任务前必须切换并核验 FSM 指纹。

实际执行必须显式 `--execute`。每个槽位在切策略、reset 或运行任务前持久化 CLAIMED，
每次终态均封存命令、episode、原始 JSONL 差量、模型使用和回执后再提交。
同一采集目录只有一个 runner 可持锁；已完成、已停止、未知尾部均不自动重新发送。
只有在已提交终态边界产生 PAUSED 的任务可续跑，续跑重新核对证据与 idle/released carry。

目标任务的已知失败完整保留，可在新健康门与 reset 确认后继续下一个已登记槽位；
失败不补采。源任务回测失败、信号、客户端 timeout、未知/隔离传输或审计异常立即停止。
未知时计数明确为 UNKNOWN_TOTAL，不能将未确认 episode 当零样本或成功。
每个已认领槽位消耗预登记的完整原生配额，不能拿失败或少执行的剩余额度新增任务。

既有 ¥5 预算不重置。新增调用自 register 起跨两臂、跨续跑累积；¥0.25 上界阈值在
逻辑任务边界检查，包含完整 T3，不是逐 API 的额外硬上限，也不是实际账单。
输入/输出 token 缺失与 GPU/实际 API 费用未知均保留。源码、模型、校准身份变化拒绝续跑。

## 本机入口

所有运行在 WSL 权威工作区，source 不接管道：

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/133_bounded_runner.py dry-run \
  --package setup/acceptance/qualification_inputs_20261007/inputs \
  --expected-sha256 3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f
```

登记需要填写实际 Windows feature 完整提交 SHA：

```bash
python3 setup/133_bounded_runner.py register \
  --package setup/acceptance/qualification_inputs_20261007/inputs \
  --expected-sha256 3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f \
  --out /home/ros/fc_sync_logs/bounded_development_next/run \
  --history /home/ros/.ros/flexcell/episodes \
  --budget "$FLEXCELL_LLM_BUDGET_FILE" --revision <完整feature提交SHA>
```

只读 run/status 不激活 ROS adapter。显式执行先运行两段 T1，形成真实边界暂停；
随后同一目录继续尚未执行的 T3 和 S1，没有重新发送已完成任务。

```bash
python3 setup/133_bounded_runner.py run --root /home/ros/fc_sync_logs/bounded_development_next/run
python3 setup/133_bounded_runner.py run --root /home/ros/fc_sync_logs/bounded_development_next/run --execute --max-slots 2
python3 setup/133_bounded_runner.py status --root /home/ros/fc_sync_logs/bounded_development_next/run
python3 setup/133_bounded_runner.py run --root /home/ros/fc_sync_logs/bounded_development_next/run --execute
```

家用 GPU 离线时，先确认本机 idle/released，再将 owned fleet 切到 FSM 0.85；
登记时加 `--order local-first`，执行使用 `--max-slots 3`，在三份 FSM 逻辑任务后暂停，
最多消耗五份原生配额。不要立即执行 Hybrid；恢复后只续跑同一日志中的未认领槽位。
源任务失败、未知终态或信号仍会 STOPPED，不能因 GPU 离线跳过这些门。

`--predecessor <旧run目录>` 只接受 REGISTERED→STOPPED、零认领、零完成、无 attempt 的旧记录，
新 plan 固定旧 plan/events 的摘要；旧文件变动拒绝执行。旧失败留在原处，不覆盖或续跑。
若旧任务已有认领、终态或未知尾部，禁止借此选项重建任务。已封存的源码身份不同，
旧实录只能审阅，不能使用新执行器继续其 STOPPED 日志。

`development_complete` 描述六个槽位均已处理，`all_trials_succeeded` 描述实际终态全部成功；
两者分开。两臂不同运行指纹与校准 cell 独立保留，不能合池报告资格成功率。
候选公开、独立保管与预算信封未核定、NET-001 和 GRASP-B-001 未解决；
`ready_for_large_test` 永远为 false，AC@90 仍 NOT_RUN。

[本机实录证据](../setup/acceptance/bounded_runner_20261007/README.md)保留真实执行结果和所有失败。
