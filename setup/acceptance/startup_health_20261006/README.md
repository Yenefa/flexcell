# NET-001：学校 Clef 启动探测的显式截止时间

当前 GPU 节点实际使用 DERP(tok)，三次 Tailscale ping 为 1.153s/421ms/377ms，
未建立直连。CLI netcheck 的本地 UDP 测试通过，但不足以识别哪一端或路径阻止
了直连。DERP 是无法直连时的中继路径，常比直连慢；见
[Tailscale 官方连接类型](https://tailscale.com/docs/reference/connection-types)。
直连失败根因 **UNKNOWN**，网络稳定性 **NOT_ACCEPTED**。

原 `ClefBackend.health()` 将 TCP deadline 限为 2 秒。此次对照第一条仍超时，
随后显式 10 秒探测在 2.337s 完成；后两对均成功。固定顺序的三对样本不是可靠性
验收，旧失败全部保留。CLI 继承代理；仅诊断子进程去掉代理的 netcheck 仍指向
Nuremberg，没有据此改动宿主、Tailscale 服务、mirrored 网络或 campus proxy。

新 `contracts/backend_health.py` 在执行器启动时读取部署明确设置的
`FLEXCELL_JEV_HEALTH_TIMEOUT_S`，缺省或其他后端仍使用原 health 方法。
deadline 为该值与推理 timeout 的较小者，非法值失败关闭，单次探测不重试。
它只验证 TCP 可达，不代表推理成功或 route_eligible。部署 manifest 记录有效值。

学校 profile 已备份后加 `FLEXCELL_JEV_HEALTH_TIMEOUT_S=10`，推理仍为 45 秒。
`jev_backends.py` **未改**，prompt SHA 仍为
`b37e71cd0b9b0ff81cfa3638111da8375251be2fadeabc01468ce46b5f4e85b8`；
原 calibration SHA `34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`
有效，route_eligible(0.85)=true，domain=45，字面 tailnet IP proxy bypass=true。

只补实际安装树的 `task_fsm_server.py` 和新 helper，两者先备份；34 个安装源码与
权威工作区逐字节一致，没有同步或删除整个 install。新的 Hybrid 0.85 部署启动
记录在 `run/deployment.json`、`run/fleet.log`，启动 probe 确认可达；新指纹独立报告，
不与 T1 的旧指纹并池。此次网络修正没有推理调用或机器人 episode。

12 项针对性测试通过；重建并测试 flexcell_skills 的 pytest 为 260 passed。
colcon test-result 聚合为 338 tests / 0 errors / 0 failures / 9 skipped，其中其他
包结果来自之前运行，不能称为本轮重跑了全部 338。原始输出均保留。

证据中的 netcheck 公网端点已脱敏，完整原始文件及其摘要保留在
`/home/ros/fc_sync_logs/school_network_20261006`；完整多节点 status 不进仓。
不含凭据、权重或编译产物。相对路径 SHA256 清单及
`scripts/verify_frozen.py` 用于复核确切文件集合。
