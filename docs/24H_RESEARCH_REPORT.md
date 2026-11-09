# 24H RESEARCH REPORT（2026-11-09 22:54 → 2026-11-10 03:10，实际约 4.3 小时）

> 中止原因：**API 额度耗尽（HTTP 402 Payment Required）**，按安全规则暂停付费模型调用；
> 其余（Gazebo/离线/分析）工作继续执行。时间窗口未用完，如实记录。

## 1. 完成内容

### P0 — Flash 统一与复现
| 项 | 结果 |
| --- | --- |
| 默认模型改为 `deepseek-flash` | 完成（`pilot/llm.py`），显式覆盖保留 |
| 运行指纹 | 新增 `requested_model` / `returned_models` / `temperature` / `max_tokens` / `tokens` / `seconds` / `key_fingerprint` |
| 离线测试 | `pytest experiments/pilot-001/tests` **29 passed**；自检 **5/5** |
| Gazebo smoke | 通过（单门 PASS） |
| E2d Flash 复现 | **PASS**，3 轮 / 3170 tokens，三门 PASS |
| E2e Flash 复现 | judge 环境失败（`owned launch exited`），未重跑（额度耗尽） |
| E2c 旧提示 × Flash | r1 judge 无效（HARNESS_ERROR），未取得有效样本 |

### P1 — 源码级修复（Level B）
- 缺陷：`task_fsm_server.py` PLACE 目标位姿固定取第一个对象区（`zone_of[self._obj_a]`）；
- **基线有效**：`dual_object` ROBOT_FAILURE、`normal` PASS、`regrasp` PASS、build OK；
- Agent 尝试 5 次（Flash×4、v4-pro×1）：**全部未修改源码**，均未通过；
- **根因（本轮最重要发现）**：Agent 工具层有三个缺陷——
  1. `_schemas()` 把工具描述写成工具名本身（模型从未收到工具说明）；
  2. 工具结果统一截断 4000 字符，而缺陷在第 53 KB / 1015 行；
  3. 缺少按内容搜索的工具；
- 三项均已修复（真实描述、分页 `read_file`、`search_code`），修复后 `search_code` 一次可定位 3 处候选、分页可显示缺陷行；
- **Level B 尚未在修复后得到一次完整成功**（额度耗尽）。

### P3-C — Track C：C12 能力检验（负结果）
| 场景 | FSM | MTC |
| --- | --- | --- |
| A 基线 dual_object | 2/2 PASS | 2/2 PASS |
| B 目标区重叠 | 0/2 安全门拒绝 | 0/2 安全门拒绝 |
| C 近距离 regrasp | 2/2 PASS | 2/2 PASS |
- **未发现 MTC 独有能力**；场景 B 由安全门在规划前拒绝，不构成规划能力检验；
- 结论按预注册记为**负结果**。

## 2. 失败内容（如实）
1. Level B 五次尝试全部失败（含 v4-pro）；
2. E2e / E2c 的 Flash 复现未取得有效 judge 结果（环境 + 额度）；
3. C12 未构造出真正的"绕行冲突"场景（场景 C 未形成冲突）；
4. 24 小时窗口只用了约 4.3 小时即因额度中止。

## 3. 研究发现
- **工具可用性是 Agent 行动缺口的重要成因**：此前把"只读不写"归因于模型倾向，
  实际存在工具描述缺失 + 读取截断 + 无搜索三个可修复缺陷；
- 该发现可解释 W5 历史数据中"8/8 失败零写操作"的一部分；
- MTC 在本场景族内未显示相对 FSM 的能力优势，此前 C3–C11 的差异应继续按"该场景下的关联"表述。

## 4. 未决与下一步
1. **额度恢复后第一件事**：用修复后的工具重跑 Level B（预注册已冻结），区分"模型能力"与"工具可用性"；
2. E2e/E2c 的 Flash 复现补跑；
3. C12 需要真正制造绕行冲突的场景（例如在两区之间放置障碍物），而非仅调整目标位姿；
4. Track B 未推进（本轮无额度）。

## 5. 证据位置
- `ci-public-window/research/evidence/`（本轮运行归档）
- `ci-public-window/research/TOOLING_DEFECT.md`（工具缺陷根因）
- `ci-public-window/research/LEVELB_FAILURE_ATTRIBUTION.md`
- `setup/acceptance/c12_capability_20261110/`（C12 负结果）
- `docs/W5E3_PREREGISTRATION.md`、`docs/W5E3C_PREREGISTRATION.md`、`docs/C12_PREREGISTRATION.md`