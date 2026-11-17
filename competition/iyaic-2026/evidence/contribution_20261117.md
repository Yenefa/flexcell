# 贡献留痕：#246 离线执行证据审计入口 + #245 动作技能目录（2026-11-16 ~ 11-17）

> 按负责人 2026-11-17 13:26 的要求「工作一定要留痕，团队协作占 20% 的分数」整理。
> 本文件只记录**可核查的事实与指针**，不改写任何原始证据；每条结论都能在 GitHub 上复核。

## 1. 认领与合作身份

| 项 | 内容 |
| --- | --- |
| GitHub 用户 | `apl12h`（Collaborator） |
| 认领 #246 | 2026-11-16 11:08 UTC 在 issue #246 留言认领（B 槽位），https://github.com/Yenefa/flexcell/issues/246 |
| 认领 #245 | 2026-11-17 06:30 UTC 在 issue #245 留言认领（A 槽位）并自指派，https://github.com/Yenefa/flexcell/issues/245 |
| 接任务前的确认 | 负责人微信授权：先修工具、正例/反例回归、原始数据保留、任务结论与审计结论分开 |

## 2. 交付物（GitHub 上可核查）

| 项 | #246 离线审计 | #245 技能目录 |
| --- | --- | --- |
| PR | https://github.com/Yenefa/flexcell/pull/264 | https://github.com/Yenefa/flexcell/pull/267 |
| base 分支 | `chore/team-handoff-20261116` | `chore/team-handoff-20261116` |
| 作者 / 创建时间 | `apl12h` / 2026-11-16 16:28 UTC | `apl12h` / 2026-11-17 06:23 UTC |
| 提交数 / 文件数 | 7 commits / 11 files（+1695 −60） | 2 commits / 6 files（+459 −0） |
| 分支 head | `63fa10ac` | `967d2c04` |
| PR 正文 | 3814 字，含两个 PR、验证记录、已知限制 | 1414 字，含范围、命令、错误码、语义边界 |

### #246 提交序列（按时间）

| 提交 | 内容 |
| --- | --- |
| `27b174e4` | 修 run 分层布局识别、结果方言、审计结论与任务结论分家 |
| `5db4c5ca` | 保留既有汇总措辞 `N passed (audit-complete)`，补分层候选路径 |
| `f535cace` | 统一入口与错误传播（第一个 PR） |
| `eca1e19b` | LONG_1 原生归档适配（第二个 PR） |
| `dd3930bc` | 把两个开放问题的判定写进 `docs/OFFLINE_AUDIT.md` |
| `fbdbc53c` | 补「乱序/重复时间戳」验收案例 |
| `63fa10ac` | 记录对已有工具的改动原因与兼容证据 |

### #245 提交序列

| 提交 | 内容 |
| --- | --- |
| `18f5f26f` | 只读动作技能目录：`load_catalog` / `list_skills` / `get_skill` + CLI + 10 例测试 |
| `967d2c04` | 新增「与源码的核对」表，把每个值对到接口、`validate_request` 与归档 README |

## 3. 做了什么（大白话）

1. **定位数据报错原因**：审计工具把 `skills/` 误认成 run、把 `OUTCOME_SUCCEEDED` 当失败，导致 PASS 被误判。用三层目录证据链（窗口层 → trial 层 → run 层）和 trial-01/02 对比确认。
2. **修工具**：按负责人选定的方案改工具、不改历史数据；正例 trial-01/02 转 success，反例 trial-05（真实 budget_exhaustion）仍 failure，证明没有修过头。
3. **建统一入口**：复用现有三个工具，不重算规则；报告显式写 `diagnostic_only: true`、`robot_task_outcome: NOT_EVALUATED`，退出码只描述诊断是否跑通。
4. **接真实归档**：LONG_1 ZIP 指纹校验、安全解压到仓库外、五个只读映射写入 `normalized/`；用原生 `request_id` / `goal_uuid` / `seq` 关联，缺字段记 UNKNOWN 并说明原因。
5. **做技能目录**：只读加载 `skill-catalog/1`、按 ID 查询、列出记录；`PROPOSED` / `UNKNOWN` / `OPT_IN` / `default_enabled=false` 原样保留，进目录不等于可调用。

## 4. 验证记录（可复现）

- `python scripts/test_run_log_audit.py` → 13 tests OK
- `python -m unittest discover -s scripts/tests -p test_offline_audit.py -v` → **11 tests OK**
- `python -m unittest discover -s runtime/skill_catalog/tests -v` → **10 tests OK**
- `python scripts/test_push_progress_audit.py` → 23 cases / 0 failed；`python scripts/test_pose_stage_timeline.py` → 21 cases / 0 failed
- CI `offline-checks`（分支专属闸门）= success，两个 PR 各自最新 head 均为 success
- 真实 LONG_1：ZIP SHA 前后均为 `5bc6ae24e5c24be0f5d0acf185230e87c1565ab75b082c0414d905598cba09d4`，145 个输入文件共 256 MB 只读未改
- 归档审计输出：`issues=4`、`exit_code=1`、`robot_task_outcome=NOT_EVALUATED`（三个 INPUT_ABSENT + 一个 SOURCE_CLAIM_CONFLICT）
- 输出安全实测：把 `--out` 指向输入目录（含目录联接绕行）→ 退出码 2，`output must be outside the run directory`，输入目录零新增

## 5. 判定记录（负责人 2026-11-17 15:09 授权「你自己决定」后按代码自行判定）

- **四来源冲突**：`verdict.passed=true`、`runtime_result.status=TASK_COMPLETED`、`run_status.status=EXECUTED`、`worldstate/summary.status=INTERRUPTED` 四个值**并列保留**，不合成任务结论。依据：`run_window.py` 的通过条件需要驱动退出码 0 + `agent_claimed_success` + `verdict.passed` + 9 道 evidence gate 全 ok，审计工具拿不到 gate，挑一个来源当结论等于伪造合成。
- **`verdict.json` 归属**：属独立验收层（trial 层）产物。依据：`build_trial_evidence.py` 调 `benchmark.evaluators.evaluate` 后写 `trial_dir/verdict.json`；历史归档 `evobot_t01_baseline_b_20261111/verdict.json`、`evobot_t05_b_20261111/verdict.json` 都在 trial 根；`scripts/sim_window.py` 全文不含 `verdict`。故 run 层缺失是真实缺失，工具不改。
- 两条判定已写入 `docs/OFFLINE_AUDIT.md` 的「决策记录」节（提交 `dd3930bc`）。

## 6. 开放问题（如实留痕，未擅自改）

- LONG_1 原生归档不含三个旧工具认识的日志名，三项检查记 `NOT_APPLICABLE` + `INPUT_ABSENT`，不是工具异常。
- 仓库基线 CI 两道红灯：`offline-tests` 死在**第 15 步 `pilot-001 P1.0 measurement self-test`**，`sim-smoke` 死在**第 5 步 `All first-party packages, including native Gazebo code`**。纯文档 PR #256、#258 在**同一步骤**同样失败，说明与本次改动无关，属基线分支既有问题。
- `scripts/run_log_audit.py`、`scripts/test_run_log_audit.py`、`config/run_log_required.json` 不在 B 槽位的「独占范围」内。B 文档允许修改旧工具但要求「先提独立修复 PR」；这两处修复是入口代码**之前**的独立提交（`27b174e4`、`5db4c5ca`），原因与兼容证据写在 `docs/OFFLINE_AUDIT.md`（提交 `63fa10ac`），未拆成第二个 PR 以避免对已开 PR 做 force-push。

## 7. 过程材料（本地，未另存副本到云端）

- `ANALYSIS_NOTES_246.md`：发现过程与四段式记录（现象 / 证据 / 判断 / 待确认）
- `MY_TASK_MAP_246.md`：任务地图与阶段进度
- `LEARNING_246_复盘.md`：弄混点与查证方法复盘
- `OPEN_ITEMS.md`：待办盘点与跨会话交接
- `patch_246/`：提交前给负责人看过的本地补丁副本
- `.workbuddy/memory/2026-11-16.md`、`2026-11-17.md`：跨会话工作日志
- 关键对比截图：曾通过微信发给负责人（trial-01 / trial-02 工具输出对比）

## 8. 边界说明

两个模块都未修改物理控制、任务定义、冻结验收器或原始证据；审计工具不产生机器人任务 PASS/FAIL，技能目录不连接动作派发。两个 PR 保持打开，未合并、未关闭 issue；合并决定在负责人。
