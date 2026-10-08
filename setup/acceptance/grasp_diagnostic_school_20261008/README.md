# 学校本机 A/B 直接抓取诊断，2026-10-08

本轮实际完成两次直接 Pick，A/B 各一次，从 canonical reset 开始，完成后恢复同一状态。
两次均取得对应 action terminal、raw pick 和 measured pose/rise；六个抓取链 MoveToPose 控制器目标
全部为 status=4。每次 reset 和严格健康检查通过，已有 FSM 仿真 fingerprint 保持：
`fa0a1c6af0016f74741983d401d31ed170e5d8cdf6e52d823488b4f2ce596917`。

| 对象         | 单次结果  | attach gap (cm) | measured rise (cm) | 控制器终态/请求 |
| ------------ | --------- | --------------- | ------------------ | --------------- |
| target_box_a | SUCCEEDED | 16.4420         | 9.6587             | 3/3             |
| target_box_b | SUCCEEDED | 16.1179         | 10.3093            | 3/3             |

这使用原有 velocity_servo 磁吸仿真；attach gap 如实记录。没有 Place/完整 policy episode 或实体硬件验收。
历史 B 抓取失败本轮未复现，GRASP-B-001 继续 NOT_RESOLVED，机制根因 UNKNOWN。
两次结果不用于成功率估计、FSM/Hybrid 比较、独立 qualification 或校准。
decision latency 为 NOT_RUN，不补 0.0ms。

## 保留的失败与仪器身份

首次实现 `6e38b44b3487b864edd7537b980595c725d05e40` 的 `evidence/run` 因把多行
RESULT 当单行解析，在 Observe 后 STOPPED，Pick 数 0；复位/clear/Observe 和错误均保留。
`evidence/v1_source` 保存对应入口源码；共用依赖可从 `evidence/v2_source` 按各 plan 的 SHA 复核。
没有覆盖、补采或把该失败改写为成功。

修复身份 `b5cac91c44a57b35fa6470e82994f5248e6ed40d` 的 `evidence/run_v2` 预先固定
A→B 两个目标，plan SHA 为 `c03e722eec98000a5bb1bb11a88c6d59b00fa2ffa3e7da7707a24c7901da6ade`。
默认只读检查 rc=0；显式执行 rc=0、state=COMPLETE、pick_goals=2；重复执行 rc=2，被一次性 claim 拒绝，
前后 root 字节清单相同。每个目标的 CLI 命令、结果、原始增量日志、测量审计、Observe、复位及健康结果均封存。

随后 `73054433b067e1669cdb2641ce54404bcf8f41a7` 为后续计划加入唯一 clear 请求 ID 和失败尾部保存。
对应定向离线检查 38 passed（执行身份当时为 37 passed）。后续加固实际动作 NOT_RUN，没有再发 Pick。
实际两次试验仍属于 b5cac91 的身份；源 pin 不改写，不与新工具身份并池。
新入口对旧 source pin 的拒绝是预期，历史复核使用这里的封存源码和字节摘要。

运行栈最初不在线，`evidence/readiness.json` 保留 RunComposite unavailable。
`evidence/start_result.json` 记录恢复同配置 FSM 仿真；没有重建或改生产/安装文件。
首次封装检查漏 source 环境被 world_sha256 门拒绝，`assembly_env_error.log` 保留说明；
正式 `finalize.sh` 正确 source 后验明 38 份生产源码及 38 份安装源码匹配冻结部署。

## 暂停账本、预算和 exposure

`evidence/postcheck.json` 按文件字节摘要证明原 374 份 episode、暂停 collector/guard、校准、
持久预算及 private 输入包均未变化。新任务 episode、模型推理、预算新增 reservation 均为 0。
三个 FSM 逻辑任务、五份原生 episode 的 collector 仍 PAUSED，剩三个 Hybrid 槽位未认领。
原四份历史 receipt 封存验证见 `evidence/prior_seals.json`。

直接技能仍产生场景 exposure。四份新的 before/after Observe 独立记录，三种不同两物体布局
与 200 个 private candidate 在两物体各 1mm 判据下无重叠；首轮 Observe 与其中 canonical 布局重复。
见 `exposure_exclusion.json` 和 `v1_exposure_note.json`。这个核对只涵盖所列观察文件，未记录 exposure UNKNOWN。
未来 qualification 必须排除这些公开诊断状态；未公开 private seed/layout，private verify rc=0，独立保管仍 NOT_ESTABLISHED。

最新 tailnet metadata 显示 GPU Online=false（只读 metadata，无 TCP/inference 调用），
所以 Hybrid 在线来源门尚未实跑，NET-001 NOT_ACCEPTED。正式协议/费用信封仍未核定。
`qualification_sampling_authorized=false`、`ready_for_large_test=false`、`n_ge_50=FROZEN`。

## 复核

`summary.json` 是便于读取的摘要，结论来源为 `evidence` 的实际 JSON 与日志。
最外层 `SHA256SUMS.json` 覆盖本目录全部文件，包括内部 manifests 和两份历史 source snapshots。
凭据、private layout、权重与构建产物未复制。不要向历史计划写入新文件或编辑已封存的 raw log。
