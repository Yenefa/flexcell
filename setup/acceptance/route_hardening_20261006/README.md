# 学校笔记本路由后续推进（2026-10-06）

修复了 SendGoal 超时后仍返回策略循环、可能再次派发技能的问题。无法确认
原 goal 的接收或停止状态时，当前任务明确失败，执行器保留 BUSY 并拒绝
后续任务；晚到的接受应答只取消原 UUID，确认终态后才解除隔离。
这修复的是执行器对未知结果的处理，原 OBSERVE_B 应答丢失的 DDS/RMW
根因仍为 UNKNOWN。

生产环境继续使用本机已验证的 clef 校准、`hybrid 0.85` 和 domain 45。
最终 S1 n=5 的所有路由审计通过，clef 实际接管 22 次，DeepSeek 接管
5 次；30 次 SendGoal 全部收到接受应答，没有 SendGoal 超时。
任务结果为 **3/5 成功**，两个失败完整保留，不能把路由通过称为全链成功。

## 代码行为与验证

- 给技能 SendGoal 分配明确 UUID，记录 task run、标签和单调时钟。
  OBSERVE 服务端记录同一个 UUID，关联请求、应答、开始执行和结果。
- 超时、未知接受和结果读取异常都不交回策略重试。晚接受只取消原 goal，
  GetResult 仍使用已有的幂等重读机制，不重新 SendGoal。
- 后续任务的隔离检查位于共享 admission 锁内；恢复 IDLE 也取得该锁，
  避免检查与新任务进入之间的并发窗口。
- 确认的技能失败仍进入原有有界策略恢复；未知结果记录为 null，
  不把它当作“确定未派发”。无法确认停止时继续隔离，需要独立确认旧
  goal 状态后再采取运行栈恢复操作。

最终仅构建 `flexcell_skills`，rc=0；该包 colcon test 为
**242 tests / 0 errors / 0 failures / 0 skipped**。日志中保留既有 fork
警告。原先 11 包构建、304 项测试与 Day-2 电池未重做。

`122_sendgoal_probe.py` 使用真实 ROS action 通信，但不调用物理技能：
服务端故意延迟 0.3 秒接受，客户端 0.06 秒超时。实测只有一次 SendGoal、
一次服务端执行；取消原 UUID 后取得 status=5，再解除隔离。
`run/sendgoal_probe_final.json` 保存全过程。这是受控晚接受探针，不能
证明原始校园网丢包原因已经解决。

源码和运行时只更新选定 skills 模块，33 个 Python 源文件与运行时副本
逐字节核对一致；保留逐文件备份。没有覆盖整个 install/build 布局。
第一次同步使用了错误的相对入口，随后 `build_skills.log` 构建的是旧源，
不列作新实现的验证。修正绝对入口后的 attempt02 与 final 构建记录均保留。

## 两个独立在线批次

| 批次   | 任务成功 | clef 接管 | 慢臂接管 | clef 调用 / tokens | SendGoal 请求 / 应答 | OBSERVE UUID 对齐 |
| ------ | -------: | --------: | -------: | -----------------: | -------------------: | ----------------: |
| phase1 |      4/5 |        27 |        6 |        33 / 47,681 |              37 / 37 |                10 |
| final  |      3/5 |        22 |        5 |        27 / 38,410 |              30 / 30 |                 8 |

两个批次指纹不同，不并池、不计算合并成功率。

- phase1: `6a593fd8cfa4409c5294f50b82f0f21b43babef7e0a53dfa8428af0680d6e69f`
- final: `2d1ba0597c807f24a70ac203abb0aff335339cc56668d13cc4871f51f1f7c689`

phase1 第 4 回合 `week1_demo_v1-f42be3f5` 的 PLACE_A 返回 error 25：
`carry release service unavailable; object remains attached`。第 5 回合
保留 PICK_B 第一次 error 23 的恢复，第二次成功。

final 第 2 回合 `week1_demo_v1-471252c7` 的 PLACE hover 返回
error 30 / motion error 22：`no response from controller action`；第 4
回合 `week1_demo_v1-dc2980c5` 再次出现 carry release 服务不可用。
均原样失败，没有补采、覆盖、重命名成功或接受 -6/SIGABRT。

carry 服务进程没有在冻结 fleet 日志中退出。批次后只读探针的五次短时间
查询均显示外部发现与 PLACE 自身依赖就绪，但不能重建失败当时的状态。
两类 PLACE 失败根因仍为 UNKNOWN，独立调查入口在
`FOLLOWUP_CARRY_RELEASE.md`，没有发布外部 issue。

模型决策延迟保留浮点 `perf_counter_ns` 计时，final 的 27 个模型决策
p50=1920.451544 ms、p95=2575.620034 ms；排除 bootstrap。
phase1 与 V3 离线推理有短暂 GPU 流量重叠；final 没有并行离线请求。
跨指纹因果延迟比较为 NOT_RUN，不宣称耗时变化由传输修复造成。
模型冻结身份重放仍为 NOT_RUN；这里复核实际执行记录的路由身份。

## Prompt 候选：保持隔离，未部署

V3 明确每个对象必须单独 OBSERVE，不能复用上一对象的观察；V4 进一步
补充按对象组织的历史事实，没有计算或强制指定模型的下一动作。
两个候选分别调用仓库 `119_policy_eval.py calibrate --backend clef`，
只评估原同指纹历史组选出的前 3 份 episode，包括失败输入。
每个候选保留 21 次实际推理与独立 prompt 身份，未和生产校准混池。

| 候选 | 记录输入 action agreement | 留出记录 agreement | OBSERVE 概率 | 中 bin 校准 n / 下界 | 结论         |
| ---- | ------------------------: | -----------------: | ------------ | -------------------- | ------------ |
| V3   |                     21/21 |                5/5 | 约 0.51–0.52 | 3 / 0.438494         | NOT_PROMOTED |
| V4   |                     21/21 |                5/5 | 约 0.60–0.62 | 3 / 0.438494         | NOT_PROMOTED |

动作纠正没有转化为足够校准置信度，无法证明减少 0.85 门下的慢臂升级。
因此停止该候选扩展，保留试验结果，未降低阈值或修改 bins。
两次候选使用同一历史留出输入，明确标记不再是盲测，不能声称泛化
准确率或物理成功率。剩余 2 份输入仅为原计划 extension，未运行。

活动校准 SHA256 为
`34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`，
prompt digest 为
`b37e71cd0b9b0ff81cfa3638111da8375251be2fadeabc01468ce46b5f4e85b8`。
V3/V4 的源文件字节、独立校准和选择记录均在 `prompt_candidates/`。

## 证据与复核

`phase1/`、`final/` 各自保留五个 episode、原始 batch、平铺 decisions、
技能日志、部署、fleet 日志、完整 skills 源码快照和审计。
phase1 原始 carry context 因早期筛选器仅用单调计数而包含以前启动的
历史记录，原文件保留；`carry_current_boot.jsonl` 另用 wall-date fence
排除旧启动记录。历史 context 不计入指标，wall time 不计算 latency。
final 筛选器同时使用日期范围分辨启动来源。

`run/` 保留全部已完成验证日志、受控 ROS 探针与只读依赖查询。
`SHA256SUMS.json` 覆盖所有冻结产物；凭据、模型权重和编译产物未入库。
权威运行源码 HEAD 仍为 `ffde775` 加上述已散列的 delta，Git 交付位于
Windows clone 的 feat 分支，未推 main。

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/acceptance/route_hardening_20261006/scripts/verify_frozen.py
```

n≥50/400 批次继续冻结。当前活动栈为已经校准的 `hybrid 0.85`。
