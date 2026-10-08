# 学校本机的有界 A/B 抓取诊断

`setup/136_grasp_diagnostic.py` 在原 FSM 0.85 仿真身份下各执行一次 A、B 的直接 Pick。
这用于补齐 GRASP-B-001 的失败阶段证据：接近、实际 attach gap、carry 确认、lift 控制器终态、
物体抬升前后位姿。模型不参与本次诊断。两次单技能结果不用于估计成功率或比较 FSM/Hybrid。

固定顺序为 A 然后 B，每次从 canonical reset 开始，clear injection 后读取新 Observe。
Pick 完成且终态与 raw pick/controller 日志匹配后，再读取 Observe 并 reset。
reset 是抓取后的生命周期恢复，没有 Place 测量。参数、生产源码、校准与原 Hybrid collector 不改动。

客户端超时、未知接受状态、信号退出或控制器终态未知时立即停止，不再复位或发送下一个目标。
已知失败保留原始记录；复位及严格健康确认后可继续另一个预先声明的对象。
每个计划只能 claim 一次。进程被中断后留下 UNKNOWN_TAIL，禁止以同一计划重复试验。
成功标志、typed outcome、ROS terminal status 和正常进程退出必须一致，`-6/134/-11/139` 不接受为成功。
没有测得的位姿、rise 和 latency 不补零；decision latency 标记 NOT_RUN。

## 操作

先 source 权威目录环境，source 不接管道，并确认 ROS_DOMAIN_ID=45：

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
test "$ROS_DOMAIN_ID" = 45
```

登记新目录，revision 是包含本工具的完整 feature 提交 SHA，deployment 指向当前同身份 FSM 部署。
保护项目包含已有 episode、原暂停 collector 及 guard、持久预算、校准和 private 输入包；
这些文件在每个边界重算摘要，不复制凭据或公开 private layout：

```bash
python3 setup/136_grasp_diagnostic.py register \
  --root /home/ros/fc_sync_logs/grasp_diagnostic_school_20261008/run \
  --deployment <当前FSM部署的deployment.json> --revision <feature提交SHA> \
  --protect /home/ros/.ros/flexcell/episodes \
  --protect /home/ros/fc_sync_logs/local_fsm_active_20261008 \
  --protect /home/ros/.config/flexcell/deepseek_budget_20261001.json \
  --protect /home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json \
  --protect /home/ros/fc_sync_logs/qualification_private_20261008/inputs
```

登记返回 plan_sha256；默认 run/status 仅验证文件，不调用 ROS 或模型：

```bash
python3 setup/136_grasp_diagnostic.py run \
  --root /home/ros/fc_sync_logs/grasp_diagnostic_school_20261008/run \
  --expected-sha256 <plan_sha256>
```

显式加 `--execute` 才开始两次 Pick。每个动作保存 CLI 命令/结果、完整增量 raw log、
实际 measured 字段、Observe exposure、复位和严格健康结果。原始日志的既有字节前缀也必须保持。
执行后封存整个诊断目录，公开摘要中必须标明真实终态、失败、STOPPED 和 NOT_RUN。

## 证据边界

直接技能不生成任务级 EpisodeRecorder 文件，但 Observe 仍构成场景暴露。
`exposure_before/after.json` 单独保存，未来 qualification 划分必须排除这些状态；不能以 episode
文件数没变声称没有新暴露。已有 private 包只承诺“现有 episode 内无近重复”，不声明独立保管，
这轮仍须私下核对新暴露是否重叠，公开核对结果时不泄露 private seed/layout。

两次成功也不能解释历史 B 抓取故障。机制根因继续 UNKNOWN；NET-001、Hybrid 在线验收和正式协议
仍未完成，`ready_for_large_test=false`，`qualification_sampling_authorized=false`，`n_ge_50=FROZEN`。
