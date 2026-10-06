# 学校笔记本：控制器 goal 隔离、DDS 与校时冲突修复

此前校准门已经打开，clef 能真实接管决策；剩余的执行失败包括控制器
SendGoal 无应答和 PLACE 无法发现 carry release 服务。本次把未知控制器
goal 纳入隔离，并在 PLACE 携物移动前检查其自身 participant 的释放依赖。

## 代码行为

- `MoveToPoseServer` 为控制器请求分配 UUID，只发送一次 SendGoal。接受应答
  超时或异常时保留原 future，返回 STATE_UNKNOWN，并阻止新的运动请求。
  晚接受时取消原 goal，读取同一 goal 的终态后才允许重新确认实际机械臂状态。
  accepted goal 的 GetResult 使用已有的幂等读取器；取消后终态仍未知时也保持隔离。
- `controller_transport.jsonl` 独立记录控制器 UUID、运动 request/evidence、
  接受应答及终态；`move_to_pose.jsonl` 保持每个运动的最终记录格式。
- PLACE 在 approach 前与 releasing 时分别检查自身 carry release client。
  不可用时保留对象 attached 状态并失败，记录 client 状态及 graph 快照。
  graph 能列出服务不等于该 client 已 ready；不重试 release，也未增大既有超时。
- 本机 ROS 部署采用 `setup/cyclone_wsl_local.xml`：loopback、静态 localhost
  peer、禁用 multicast、自动 participant index，保留原 MTU 限制。配置字段
  对照安装版本的 [Cyclone DDS 0.10.5 schema](https://raw.githubusercontent.com/eclipse-cyclonedds/cyclonedds/0.10.5/etc/cyclonedds.xsd)。
  mirrored 网络、ROS_DOMAIN_ID=45、GPU HTTP endpoint 与 no_proxy 保持原配置。
  未使用 ROS_LOCALHOST_ONLY。本部署针对所有 ROS 节点都在本机的仿真链；
  跨主机 ROS 节点需采用相应 DDS profile。

## 已完成验证

- 修改后的 skills 包构建成功，colcon 报告 **248 tests / 0 errors / 0 failures**。
- 两个独立 ROS 进程在 domain 45 下完成 20/20 synthetic Trigger RPC。
  受控控制器延迟接受，客户端超时后保持隔离，取消原 UUID，并确认 CANCELED
  终态（status=5）；只有一个 SendGoal，physical_dispatches=0。
- 完整受管栈冷启动成功，严格 health 的 `ok:true`、`hard_fail:[]`。
  四个进程的环境与部署 DDS digest 对齐，生产 clef calibration 身份未变。
- 校时修复后的 S1 **5/5 成功**，所有命令 rc=0；clef 接管 **30 次**，
  DeepSeek 接管 5 次。实际 GPU 调用 35 次 / **50,489 tokens**，含低置信度
  后升级的提案；不存在 FSM bootstrap 冒充 GPU 调用。
- task SendGoal **40/40** 接受应答，10 个 OBSERVE UUID 与执行记录相符。
  **60 个控制器 UUID** 都有唯一 SendGoal、接受应答及 SUCCEEDED 终态，
  没有 transport quarantine。10 次 PLACE 的 preflight/releasing 共
  **20/20 ready**，没有释放依赖不可用事件。
- 决策时延 n=35，p50=2372.750ms、p95=3119.762ms，来自浮点
  `perf_counter_ns` 测量。模型重放为 NOT_RUN；这不是实体机械臂验收。

在线结果见 [final/audit.json](final/audit.json) 与保留的 batch、episode、
扁平 decisions 和原始日志。校时修复前后的批次使用不同指纹，分开报告。
失败全保留，不补采，不与前两批或旧校准身份并池；n≥50 继续冻结。
历史 DDS/RMW/NIC 故障根因仍为 UNKNOWN，本配置通过不能证明此前由网卡选择导致。
决策时延仅使用带 `perf_counter_ns` 标记的浮点毫秒，不做跨指纹因果比较。

## 新发现：重复校时导致系统墙钟跳变

第一批计划 S1:5，在一个失败 episode 后，第二次 reset 失败，runner 自动停止。
原始记录在 `failed_batch/`：快臂接管 2 次，真实快臂调用 3 次 / 4,038 tokens，
task SendGoal 3/3 确认，控制器 4 个 UUID 全部有接受应答和 SUCCEEDED 终态。
PLACE preflight 的 release client 为 ready。失败发生于 descend 的 MoveIt
规划（error=99999 / ERR_NO_COLLISION_FREE_PLAN），没有发送 descend 控制器 goal。
下次 reset 报 scene apply false 和 arm home false，其中 homing 执行器因缺少
足够新的 joint state 而 ABORTED。不能将该批记成 n=5 或用后续结果覆盖。

随后 25 秒只读观测发现墙钟反复跳变约 ±18.6 秒，共 10 次；同期 ROS
`/clock`、`/joint_states` 各一个发布者，消息时间戳没有倒退。内核启动参数
为 `hv_utils.timesync_implicit=1`，而 WSL 内 `systemd-timesyncd` 同时 active，
其 NTP offset 约 -18.64 秒。
[Ubuntu 官方 WSL 校时说明](https://ubuntu.com/wsl/docs/stable/explanation/time-sync/)
明确建议在 Ubuntu 24.04 使用 Hyper-V 宿主校时时停用该服务以避免冲突。

已执行 `sudo systemctl disable --now systemd-timesyncd.service`，留下唯一宿主
校时来源。Windows 时间及 WSL 网络配置未改；变更前后状态、命令输出、回滚
命令在 `validation/time_authority_change.json`。切换后的观测保留一次约
+18.67 秒的宿主校时交接，随后近 25 秒没有再次跳变。

`102_mainline_runtime.sh` 将 Hyper-V implicit 参数、timesyncd active 状态与
部署脚本本身的 digest 纳入运行指纹。冷启动清除原运行的时间状态后再验证，
校时修复前后的批次严格隔离。这确认了重复校时冲突的存在；原 DDS/RMW
无应答、规划空间及 B 抓取的各自历史根因不能据此全部归因。
最终批次结束后再观测 25 秒，墙钟跳变 **0 次**，ROS 消息时间戳倒退 **0 次**，
结果在 `validation/clock_probe_postbatch.json`。

## 部署、证据与复核

`scripts/deploy.py` 只备份并同步两个 skills 模块及相关测试/探针/config，
在 `mainline_physics.sh` 中切换 DDS profile；未同步或删除整个 install 树。
旧 profile 和模块在 `validation/backup/`，实际 runtime 和 DDS 身份在
`validation/cold_identity.json`（修复前）和 `validation/clock_fixed_identity.json`
（最终）。凭据、模型权重与编译产物不入仓。

`validation/activation_attempt01.txt` 保留部署脚本相对路径 ENOENT；
`build_before_activation_attempt01` 是旧源构建，不计入本修复的验证。
首轮探针的代码与最终运行代码仅有日志分流差异，原代码和结果均保留；
`local_dds_probe_final` 使用最终代码重做受控非运动探针。
只读 clock probe 的前两次因 Jazzy 不提供假定的 publisher GID metadata
而失败，日志和各版本源码保留；最终探针明确将缺失的消息 GID 标为
UNAVAILABLE，并单独保存 graph endpoint GID。CLI daemon 的 graph 查询
未返回，空文件标为 NOT_RUN，最终 graph 来自有界 direct rclpy 探针。

`scripts/freeze.py` 按运行 ID 关联 task/decision/episode，按 controller UUID
关联请求、响应、终态，并保留运行前字节 offset 后的所有原始日志。
`SHA256SUMS.json` 在文档 prettier 完成后封存，复核命令：

```bash
python3 setup/acceptance/place_transport_20261006/scripts/verify_frozen.py
```
