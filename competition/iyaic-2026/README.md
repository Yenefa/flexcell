# FlexCell · IYAIC 2026

比赛是 FlexCell 的阶段性交付，长期项目定位保持 **Agentic Flexible Robotic Workcell**。
本目录收敛比赛场景、材料、演示与只读证据；通用能力留在 `src/flexcell/`，原始实验留在 `setup/acceptance/`。

**交付状态：PREPARATION / NOT_READY。** 尚无比赛部署 tag，未完成现场或实体硬件验收。
2026-10-17 审阅基线为 `a9b6a6255d91a568e44eea555ecb33f7e0d7d49f`。

## 入口

- [执行计划与任务追踪](PLAN.md)
- [两个演示场景与运行边界](demo/README.md)
- [项目创意计划书初稿](materials/project-plan.md)
- [PPT、视频与答辩提纲](materials/presentation.md)
- [家用快模型连接与交付检查](RUNBOOK.md)
- [E-021 只读归档审计](evidence/e021-audit.json)

## 比赛条件及来源

[河南赛区官方通知](https://iyaic.com/nd.jsp?fromColId=2&id=152)确认：报名截止 **2026-11-13**，
比赛 **2026-11-21–22**；河南全日制在籍研究生/本科生/专科生，同校学生最多3人、指导教师最多2人。
报名锁定后人员不可更改。成赛线下、未成赛可能转线上统筹，后续安排需核对通知。
报名截止不自动等于项目材料提交截止。

用户提供的创意组安排：自主命题，计划书/PPT及可选Demo或视频，约8分钟展示答辩；
评分为创新25%、技术可行性20%、实用15%、完成度15%、团队协作20%、答辩5%。
**赛项细则与提交格式尚待正式核对**，上述评分不标作本轮独立官方核验。

## 仓库策略

选择主仓 `competition/iyaic-2026/`，不新建比赛仓库，不维护永久比赛分叉。
开发使用普通 PR 分支，赛前 tag 固定版本；比赛结束后本目录保留为可追溯案例。
展示层不能覆盖 Skill、验证容差、安全门或恢复预算。

| 能力                                                     | 实现/交付位置                                                         | 可说的结论                 |
| -------------------------------------------------------- | --------------------------------------------------------------------- | -------------------------- |
| FSM/Jev/Clef/LLM/Hybrid、统一执行、安全门、验证、episode | main 审阅基线                                                         | 已有实现，完整 M3 未验收   |
| 防止零快臂调用冒充 Hybrid                                | [PR #28](https://github.com/Yenefa/flexcell/pull/28)                  | 待合并；运行指纹更新后重验 |
| 抓取探针动作终态与证据                                   | [PR #29](https://github.com/Yenefa/flexcell/pull/29)，依赖 #28        | 待合并；物理根因未知       |
| T1/T3、组合任务、确认边界暂停续跑                        | [TransferBench 分支](https://github.com/Yenefa/flexcell/tree/01fd76f) | 有界仿真试点，未合入 main  |

现有 T1/T3 小试点双方成功。T3 外层计划由调用者提供，模型决定段内动作；不称自主生成组合计划。
Observe/Verify 用仿真真值，carry 为 magnetic simulation，不称视觉、接触抓取或实体安全验收。

## 证据纪律

保留 FSM 控制臂、统一契约、安全门、独立验证、恢复预算、全部失败和原始证据。
`FSM_ACTION_AGREEMENT` 只衡量动作一致，不是物理成功概率。
Hybrid 付费节省以纯 LLM 为对照，本地推理仍有硬件/能耗/时延成本。
不同 protocol/fingerprint/calibration 不并池；T3 一条整链只算一个逻辑任务。
`n≥50`、AC@90 和正式资格保持原冻结状态；比赛目录不授予新的采样资格。

E-021 为双物体 S1 描述性先导：FSM 19/20、Hybrid 0.03 18/20、Hybrid 0.85 17/20，
区间重叠且顺序运行，未证明策略优越。完整原生 episode 的归档仍缺失，详见审计报告。
