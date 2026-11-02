# D3 当前证据台账

核对日期：**2026-11-02**。结论仍为 **NO_GO_FOR_DEFAULT_ADMISSION**，默认后端不变，
n≥50 模型实验继续冻结。此页汇总证据，不作新的 GO 裁决，也不关闭 #56–#59。

当前 `main` 为 `4e7800058ca87e264ae7fa0bb5297facee7d4b51`。下述 #75–#88
是尚未合入主线的 PR/分支证据；功能实现、某窗通过和主线准入是三个不同状态。
原 [2026-10-27 决策](DETACHABLE_ADMISSION_20261027.md) 及 HANDOFF 数字原样保留，
其“尚未实现/缺失”等描述按当日快照理解。准入条件以 [#57](https://github.com/Yenefa/flexcell/issues/57) 为准。

| #57 判据 | 实现和实际观测 | 来源 / 版本 | 边界与仍缺证据 |
| --- | --- | --- | --- |
| 1. 五次 attach/detach/reattach，每次绑定前父子不接触 | native 生命周期、预定位和原始接触门已实现。#85 基线与修复各一次 A/A/B/B/A 五循环，两窗均 `FIVE_NATIVE_CYCLES_PASS`；每流 83,339 / 83,354 个连续 2 ms 步，绑定 4–8 ms | [#85 胶囊](../setup/acceptance/native_audit_20261031/)，运行源码 `19caa01` / `3328693` | 静止臂 native fixture 的结果；不能拼成运动臂五循环或接触抓取资格。历史 CI 失败保留；完整 D3 未合格 |
| 2. 预定位 SE(3) 基准后保持 ≥10 s，漂移 <2 mm / <1° | #77 加基准，#81 修世界静止与 q/-q。#81 一次**新** A 抓放：跟随 17.30 sim s，原始附着 8,665 步，最大平移 0.081796 mm、转角 0.295487 mrad；落点 5.146469 mm。100 ms 原始 hold 的 parent 世界散布 0.057469 mm / 0.707184 mrad | [#81 回放](../setup/acceptance/preposition_world_20261031/verify.py)，源码 `19caa0199660c6a0d9d95af14620695dde0eedcf`，窗口 `56693027e5444c3ca559acd3a4f6b1ad` | #77 对旧窗口再推导不是执行新 latch。#81 仅一次有界成功；在线 80 ms 五样本与原始 100 ms 门不能互换。#88 两个拒收边界仍有效，见下文 |
| 3. 释放后 0.5 s 内自由落体，a_z = −9.8±20% | #81 同轮 contact/motion 门通过 9,411 步，21 点 / 40 ms 拟合 −9.800000 m/s²；#85 两窗也保留逐轮释放 fit | [#81 原始回放](../setup/acceptance/preposition_world_20261031/)，[集成方法](INTEGRATED_CONTACT_WINDOW_20261030.md) | 对已声明 fixture 的观测，不能证明任意接触/负载或真实机械臂；不得用分离的重力探针替换缺失的同轮释放证据 |
| 4. 500 Hz，无 >1 m 跳变或 NaN 接触力 | 2 ms physics/contact 同步记录和空/缺传感器区别已实现。#81 28,197 连续原始步，无缺步，完整回放通过。#79 已知重力方向控制：501 个 settled 样本，z 约 0.49 N，方向余弦 1.0，侧向 3.6e−16 N | [#81 胶囊](../setup/acceptance/preposition_world_20261031/)，[#79 力校准](SIGNED_CONTACT_FORCE_20261031.md) | #79 **仅校准已知重力方向**，侧向/斜向/力矩及一般接触抓取均未校准；无传感器仍 UNKNOWN。不能把多个 cohort 拼成全系统准入 |
| 5. 不放宽容差的 legacy Pick/Place 对照 | #80 是 **MTC skill × 三种 carry**。#86 补了本机 **legacy skill × teleport/joint**；实际 verify 容差均 60 mm，四格读数见下表 | [#80 回执](../setup/acceptance/legacy_parity_20261031/)，[#86](https://github.com/Yenefa/flexcell/pull/86)，[封存复算](../setup/acceptance/native_portable_20261101/legacy-review.json)，复核源 `d9f504c` | [#59](https://github.com/Yenefa/flexcell/issues/59) 的 CI 执行条件仍未完成。搬运后缺回执仍 PASS 的报告器缺陷由 [#89](https://github.com/Yenefa/flexcell/pull/89) 收紧；报告 PASS 不替代执行和准入 |
| 6. A/B 独立、退役会话不可复用 | native fixture 已覆盖 A/B 独立通道、跨对象/退役 release 与 re-engage 拒绝、租约失效；#85 两窗继续核对所有权 | [初始 fixture](../setup/acceptance/trusted_sim_20261027/)，[#85 胶囊](../setup/acceptance/native_audit_20261031/) | PASS 只属于该 fixture；不扩大为任意并发调度/真实设备资格，也不单独构成 D3 GO |

## 对照矩阵：描述读数，不作因果排名

下列最大误差来自已提交的原始 verify rows，每格五次 placement；共同容差 **60 mm**。
旧 HANDOFF 中 joint 的 2.16–2.25 mm 只覆盖部分单物体结果，遗漏了双物体最大值。

| skill / carry | teleport 最大误差 | detachable_joint 最大误差 | 执行边界 |
| --- | ---: | ---: | --- |
| MTC（#80） | 0.170952 mm | 12.252029 mm | 本机五例窗口；不是 legacy 技能验收 |
| legacy（#86） | 12.206467 mm | 45.006972 mm | 本机五例窗口；#59 的 CI 条件未完成 |

相同 skill 换 carry 的最大值差为 12.081 / 32.801 mm；相同 carry 换 skill 为
12.036 / 32.755 mm。两组接近且最大值可能来自不同落点，不能据此说“skill 是主要因果项”，
更不能推导成功率或下一窗失败概率。有限窗口的机制归因仍 UNKNOWN。

## guard 故障链、历史 CI 与来源边界

- [#78](FALSE_ATTACH_INJECTION_20261031.md) 验证的是 **guard 输入的上报 pose** 被推移
  30 mm 后的拒绝、取消、确认运动终端和不派 PLACE 的链路。原始 2 ms 物理数据不变；
  本机一次窗口有 10 个注入帧，不能称为物理打滑或接触抓持验证。**本地 S2 的同轮画面与
  故障响应联调仍待执行**；机器角色名本身不是证据。
- 历史 CI `41116653853` 第三循环 STOPPED，stale 为 **787.690270 ms**。
  两个原始流均连续 30,716 步；缺失败时堆栈和 reader tick，消费者暂停来源 UNKNOWN。
  #85 修的是已确认的大审计对象跨轮存活：两窗最大 live collect
  **385.436→104.429 ms**、live GC **362.706→98.861 ms**，墙钟 **204→208 s**。
  不声称整体加速、CI 间歇问题根治或可靠性提高。
- #85 早期 Actions `41229250750` / `41229250733` 的 **0 steps** 与上述 runtime
  STOPPED 不同；当时 annotation 指向付款失败/消费上限，具体账户条件未确定。
  不把未开始写成测试失败或 PASS，也不把历史账户拒绝当作今天所有 CI 的状态。
- #85 修复窗原版本旁车保留末尾 CR，仍标记 **INVALID_TRAILING_CR**；209 个源码 SHA
  与 Git/tar 一致的明确补证保留。后续仅对四个列明 gate 源文件作 LF/CRLF 形式绑定修复，
  原 receipt/source-binding/ZIP 字节不变。[独立 Windows/Linux Git LF 回放及 35 项反例](NATIVE_PORTABLE_BINDING_20261101.md)
  已通过；此前使用 Windows 挂载树的 Linux 回放不算独立 LF 检出。
- #75 的另一条求解器路线已在 head `10aef1e` 有绿的
  [offline](https://github.com/Yenefa/flexcell/actions/runs/41389882000) /
  [simulation](https://github.com/Yenefa/flexcell/actions/runs/41389881998) CI。
  这不能替 #86 的 literal legacy 矩阵或 S2 联调签收；#75 与 #76 有重叠求解器改动，
  后续合入前须先对齐实现与依赖，不应机械合并整个堆叠链。

## #88：任务成功，资格窗口仍 STOPPED

[#88 只读诊断](https://github.com/Yenefa/flexcell/pull/88) 源码 `66cff2e`，窗口
`8e2481ef4ed04aeaa2d9519407068c59` / `run-3edeaffca614`，仅一次 A 任务。
任务在原 60 mm 容差下 PASS，误差 **35.553473 mm**；wrapper exit 1 / 86 s，
窗口 **STOPPED / NO_GO**，无补跑。27,608 条连续 2 ms physics 和同数 contact ticks 封存。

- sampled monitor 结束 34.002 s，原始 last-attached 为 34.026 s，尾部
  **24 ms > 原 20 ms**，原门禁拒绝不变。
- 原始 100 ms hold 为 **0.497918 mm / 1.640896 mrad > 原 1.5 mrad**。
  在线 80 ms 五样本曾通过，不能替代更长原始窗口。
- 释放前水平误差 **33.294197 mm**。刚性偏移与假设竖直偏移的向量范数
  **29.663225 mm**，EE tracking **3.648824 mm**，释放后移动 **2.263584 mm**。
  必须作向量合成，不能相加范数或给因果百分比。这只解释该会话的几何账；
  #86 历史 45 mm 的唯一机制仍 UNKNOWN，生产控制尚未修。

[诊断回放入口（固定 #88 源版本）](https://github.com/Yenefa/flexcell/blob/2bc2e83514ea31a6f648034f2e4a2d9bb7805897/setup/acceptance/legacy_release_20261101/verify.py)
只用 Python 3.12 标准库；exit 0 表示 **DIAGNOSTIC_REPLAY_COMPLETE**，JSON 仍为
STOPPED/NO_GO，不是资格 PASS。此页不修改其诊断、门禁或封存字节。

## 下一步顺序

1. 完成 #82 报告器与 #84 两条现成归档回放的离线接线；分别见 #89 / #87。
   本地回放结果和 Actions 实际运行状态分开记录。
2. 按独立测试 PR 在本地 S2 做有画面的有界正常/guard 故障窗口，首次未知终端或
   非预期失败即停；不替换样本。画面仍是数据采集，不是视觉感知策略。
3. 高难度工作单独修复/验证 #88 暴露的释放监控尾段和完整 hold 覆盖，再完成 #59 的
   literal legacy CI 条件及六条同一声明下的准入证据。未齐全前不改默认、不解冻大样本。
