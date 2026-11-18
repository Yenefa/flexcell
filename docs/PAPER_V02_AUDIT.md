# EvoBot 论文 v0.2 数字对账（独立核对）

- 核对对象：`EvoBot-机器人配置修复研究-论文初稿-v0.2-20261119.md`（工作区根，32 KB，276 行）
- 核对基准仓库：`project-033-flexcell/wt-grasp-probe`，HEAD = `research/grasp-contact-probe-20261119`（`e3674e65`），基于 `origin/main ebe27f07881200ab0fc74dfaa5490208023bf9d9`
- 核对方式：只读。文件用 read 工具读，JSON 用本机 `python 3.11.15` 解析；git 只用 `log/ls-tree/show/cat-file/branch/for-each-ref/rev-list`；未运行 gz/ROS，未 commit/push，未改动除本文件与 `PAPER_V02_AUDIT.json` 之外的任何仓库文件。
- 唯一一次"执行代码"：`experiments/pilot-001/runs/p1.5-w5e2{b,d,e}-20261109/verify.py`（只读断言脚本，不写盘），三个都在本检出上失败，见 E04。
- 结论口径：**一致** = 归档数字与论文表述可逐字对上；**不一致** = 归档给出不同数值或论文表述在归档中不成立；**无法判定** = 归档存在但本机无法确证（如 GitHub 端可达性）；**说明** 类不给结论，只在"实测值"里写清楚。
- 规模：**55 条可核查断言 → 一致 51 / 不一致 3 / 无法判定 1**（逐条见下表与 `PAPER_V02_AUDIT.json`）。

## 关键前提（会影响第 6 章读法）

1. `evolution/experience` **不在** 本工作树、也不在 `ebe27f07`（`git cat-file -e ebe27f07:evolution/experience` 失败）。但它**存在于仓库其它分支**：`autonomous/flexcell-remediation`、`develop/validation-infrastructure-20261113`、`origin/develop/experience-learning-20261113` 等分支可达的提交里有 `evolution/experience/`（80 个文件）。
2. 论文第 6 章钉的 `779251f5e307e826213adbb8ad1075a130c293ef` **在本克隆里是悬空提交**：`git cat-file -t` 可解析（commit），`git for-each-ref --contains` / `git branch -a --contains` / `git rev-list --all` 全部为空 —— 不是任何分支、标签、远程跟踪分支的祖先。经验链的归档包 `setup/acceptance/evobot_continual_chain_20261118/` 与报告 `docs/EVOBOT_CONTINUAL_CHAIN_20261118.md` 也**只存在于该悬空提交**（`git log --all -- <该路径>` 为空）。
3. 因此第 6 章**不是"仓库当前快照无此证据"**——证据确实在对象库里、可以按哈希完整读出，我按 `779251f5:<path>` 逐项核对了 56→90 mm、60→81.4 mm、109/7、294/7、163、四条路由 2/4 等数字，全部命中。缺的是**可达性**：读者从任何分支都走不到这些文件。

---

## 大表（55 条）

| # | 论文位置 | 论文数字／表述 | 仓库证据路径 | 实测值 | 结论 | 建议改法 |
|---|---|---|---|---|---|---|
| A01 | §4 首段、§1 贡献 | 五个协议共 **17** 条 result 记录（E2 3 / E2b 3 / E2c 2 / E2d 6 / E2e 3） | `experiments/pilot-001/runs/p1.5-w5e2{,b,c,d,e}-20261109/**/result.json` | 实际 17 个 `result.json`：3/3/2/6/3；无缺、无多 | 一致 | 无需改 |
| A02 | §4 表 | E2 **0／3** | `runs/p1.5-w5e2-20261109/aggregate.json` + 3 个 `result.json` | `aggregate.json` 无 `success` 字段，`status:"BLOCKED"`、`n:3`；3 条 `result.json` 全 `success:false`、`verdict.passed:false` → 0/3 | 一致（0/3 由 result.json 推定，aggregate 本身不含通过计数） | 可在脚注写明 E2 的 0/3 来自 3 份 result.json，aggregate 只给了 BLOCKED |
| A03 | §4 表 | E2b **3／3** | `runs/p1.5-w5e2b-20261109/aggregate.json` | `success:3`，三行 `target/regression` 均 PASS，`config_ok:true` | 一致 | 无需改 |
| A04 | §4 表 | E2c **0／2** | `runs/p1.5-w5e2c-20261109/aggregate.json` | `success:0`，两行 `target:ROBOT_FAILURE`、`reg_normal/reg_regrasp:PASS`、`wrote:false` | 一致 | 无需改 |
| A05 | §4 表、§5.1、摘要 | E2d **6／6** | `runs/p1.5-w5e2d-20261109/aggregate.json` | `success:6`，六行三门全 PASS，模型 {chat×4, v4-pro, flash} | 一致 | 无需改 |
| A06 | §4 表、§5.1、摘要 | E2e **3／3** | `runs/p1.5-w5e2e-20261109/aggregate.json` | `success:3`，三行三门全 PASS，模型 {chat×2, flash} | 一致 | 无需改 |
| B01 | §4.1 表 行1 | E2d-1 chat / **3** 轮 / **3,089** tokens / 三门通过 | `runs/p1.5-w5e2d-20261109/rep1/result.json`、`rep1/verdict.json` | `iterations:3`、`cost.tokens:3089`、`verdict.passed:true`、target/regression_normal/regression_regrasp 全 PASS | 一致 | 无需改 |
| B02 | §4.1 表 行2 | E2d-2 chat / **2** 轮 / **1,999** | 同上 `rep2/*` | 2 / 1999 / 三门 PASS | 一致 | 无需改 |
| B03 | §4.1 表 行3 | E2d-3 chat / **2** 轮 / **1,983** | `rep3/*` | 2 / 1983 / 三门 PASS | 一致 | 无需改 |
| B04 | §4.1 表 行4 | E2d-4 chat / **3** 轮 / **3,069** | `rep4/*` | 3 / 3069 / 三门 PASS | 一致 | 无需改 |
| B05 | §4.1 表 行5 | E2d-5 **v4-pro** / **3** 轮 / **3,511** | `rep5-v4pro/*` | 3 / 3511 / 三门 PASS；`meta.model:"deepseek-v4-pro"` | 一致 | 无需改 |
| B06 | §4.1 表 行6 | E2d-6 **flash** / **3** 轮 / **3,132** | `rep6-flash/*` | 3 / 3132 / 三门 PASS；`meta.model:"deepseek-flash"` | 一致 | 无需改 |
| B07 | §4.1 表 行7 | E2e-1 chat / **4** 轮 / **4,063** | `runs/p1.5-w5e2e-20261109/rep1/*` | 4 / 4063 / 三门 PASS | 一致 | 无需改 |
| B08 | §4.1 表 行8 | E2e-2 chat / **4** 轮 / **4,060** | `rep2/*` | 4 / 4060 / 三门 PASS | 一致 | 无需改 |
| B09 | §4.1 表 行9 | E2e-3 flash / **4** 轮 / **4,321** | `rep3-flash/*` | 4 / 4321 / 三门 PASS（该目录无 `execution.log`，不影响判定） | 一致 | 可在数据可得性脚注注明 rep3-flash 少一份 execution.log |
| B10 | §4.1 末句 | "最终 verdict 的目标、normal、regrasp 状态均为 PASS" | 9 份 `verdict.json` | 值全 PASS；但 `verdict.json` 的键名是 `target / regression_normal / regression_regrasp`，`aggregate.json` 才用 `normal / regrasp` | 一致（仅字段命名差异） | 表头改为 "目标 / regression_normal / regression_regrasp（aggregate 记作 normal、regrasp）"，避免读者按名字找不到字段 |
| B11 | §5.1 | E2d 交互轮次 **2–3**，中位数 **3** | `aggregate.json` `iters` | [3,2,2,3,3,3] → min 2 / max 3 / 中位数 (3+3)/2 = 3 | 一致 | 无需改 |
| B12 | §5.1 | E2d token **1,983–3,511**，中位数 **3,079** | `aggregate.json` `tokens` | 排序 1983,1999,3069,3089,3132,3511 → 中位数 (3069+3089)/2 = **3079** | 一致 | 无需改 |
| B13 | §5.1 | E2e token **4,060–4,321**，中位数 **4,063**；轮次均为 4 | `aggregate.json` `tokens/iters` | 4060,4063,4321 → 中位 4063；iters 全 4 | 一致 | 无需改 |
| C01 | §4 表、§3.2 | E2 **每条实际运行 4 轮** | `runs/p1.5-w5e2-20261109/aggregate.json`（`pilots[].iters=4,4,4`）、`pilot{1,2,3}-?result.json`、`manifest.json` `task_budget.T-W5E2.max_iterations=4` | 记录 iterations=4/4/4，manifest 上限亦为 4 → 与论文相符。**但** E2 `aggregate.json` 的 `reason` 自述 "frozen protocol caps iterations at <=3"，与 manifest（4）和记录（4）互相矛盾 | 一致（论文侧正确；归档内部有矛盾） | 论文可加一句："E2 的 aggregate 自述上限 ≤3，与实际 manifest（4）不符，本文按 manifest 与记录记 4 轮" |
| C02 | §4 表 | E2b **6 轮**；最小配置覆盖；提示无需查看 gate；双门 | `manifest.json task_budget.T-W5E2B.max_iterations=6`；`pilot/w5e2.py build_t_w5e2b`（`config/week1.yaml` 只写 `zone_2_*` 三行覆盖，task.md 写明 "gate/ is read-only and does NOT need to be inspected"）；`ACCEPT` 仅 dual_object+normal | 预算 6；实际 iters 5/3/3；提示文本与双门实现均与论文相符 | 一致（"6 轮"是预算上限，实际未用满） | 表头加"（预算）"，或在表下注 "E2b 实际轮次 5/3/3" |
| C03 | §4 表 | E2c **6 轮**；回归增加 regrasp；无成功写入 | `aggregate.json`（iters 6/6、`wrote:false`、`reg_regrasp:PASS`）；`w5e2.py ACCEPT_C`（dual_object+normal+regrasp）；`rep{1,2}/events.jsonl` 末轮 calls 无写工具 | 6/6；三门；末轮累计调用中 write_file/edit_file 计数 = 0 | 一致 | 无需改 |
| C04 | §4 表、§4 末段 | E2d 6 轮；提示给出操作顺序与可用数值范围；三门；原协议最多 2 次后扩到 6 | `docs/W5E2D_PREREGISTRATION.md`（"最多 2 次试点"、附录 "4/4 成功（后续补 2 次）…3/2/2/3、3089/1999/1983/3069"）；`w5e2.py build_t_w5e2d` task.md（"First run the target scenario once…set zone_2_x to a reachable value (0.20-0.25)"） | 预注册上限 2、实际 6 条；提示原文与论文描述逐条对应；附录前 4 条的 iters/tokens 与 rep1–rep4 完全一致 | 一致 | 无需改 |
| C05 | §4 表、§4 末段、§6.6 | E2e 6 轮；对象注册缺失且键名已告知；三门；先 2 次 chat 后加 flash；探测不进分母 | `docs/W5E2E_PREREGISTRATION.md`（"先用 deepseek-chat 2 次"、附录 "3/3…4/4/4、4063/4060/4321"）；`runs/p1.5-w5e2e-20261109/probe.json`（`ERR_SAFETY_REJECTED / target_not_available`）；`aggregate.json n:3` | 分母 3 条不含 probe；probe.json 明写 "no agent, not part of statistics"；task.md 点名 `observe_server tracked_objects` | 一致 | 无需改 |
| C06 | §3.2 | E2b–E2e 清单声明最多 **6** 次交互、**20,000** tokens，token 在一次 step 返回后检查 | `manifest.json task_budget.T-W5E2{B,C,D,E}`；`pilot/runner.py:106-109` | 四项均 `max_iterations:6, max_tokens:20000`；runner 在 `agent.step()` 之后累加并判定超限 | 一致 | 无需改 |
| C07 | §3.2 | 可达性缺陷把 `zone_2_x` 设为 **0.45 m**；E2d 提示要求先执行目标再设入 **0.20–0.25 m** | `pilot/w5e2.py`（`OVERLAY zone_2_x: 0.45`、`build_t_w5e2` 里 `zone_2_x: 0.25→0.45`、E2d task.md "0.20-0.25"） | 0.45 与 0.20–0.25 均逐字命中 | 一致 | 无需改 |
| C08 | §3.2 | 对象缺陷使 `tracked_objects` 只保留对象 A | `pilot/w5e2.py E2E_OVERLAY` = `tracked_objects: ["target_box_a"]` | 命中 | 一致 | 无需改 |
| C09 | §5.2 | E2 三条与 E2c 两条**无写操作**；E2b/E2d/E2e **各一次成功写入**；按 events 末轮累计调用重算 | 17 份 `events.jsonl`（`kind:"iteration"` 的 `calls` 为累计快照） | E2: 7/8/7 次调用、0 次写；E2c: 9/10 次、0 次写；E2b 3 条、E2d 6 条、E2e 3 条**各恰好 1 次** `["edit_file","config/week1.yaml"]`，无 REFUSED_PROTECTED | 一致 | 无需改 |
| C10 | §5.3 | E2c 中 normal 与 regrasp 通过而目标失败 | `runs/p1.5-w5e2c-20261109/rep{1,2}/verdict.json` | `target:ROBOT_FAILURE`、`regression_normal/regression_regrasp:PASS` | 一致 | 无需改 |
| C11 | §5.4 | 结果文件含 `false_success`，但 `FCAgent.step` 总是返回 `claim_success=False`，故 `false_success=0` 无信息量 | `pilot/agent_fc.py:59`、`:97`（两个 return 都是 `"claim_success": False`）；17 份 result.json 全部 `claim_success:false, false_success:false` | 命中 | 一致 | 无需改 |
| D01 | §6.2、摘要、结论 | 落点间距由 **56 mm → 90 mm** | `779251f5:setup/acceptance/evobot_continual_chain_20261118/03_effect_E2.json` | `baseline_min_separation_m = 0.055999999999999994`（56.0 mm）→ `applied_min_separation_m = 0.09`（90.0 mm） | 一致 | 无需改 |
| D02 | §6.2 | 最小间隙由 **60 mm 升至 81.4 mm** | 同上 `03_effect_E2.json` | `baseline_min_clearance_m = 0.06003332407921455`（60.03 mm）→ `applied_min_clearance_m = 0.08139410298049855`（**81.39 mm**） | 一致 | 无需改 |
| D03 | §6.2 | "满足 **90 mm 契约**" | `03_effect_E2.json expectations.applied_min_separation_m_gte:true`；`SUMMARY.json` `selected: "respread/step=0.090"`；`verify_result.json checks.applied_spacing_at_least_90mm:true` | 契约阈值 0.090 m，选中参数 step=0.090 | 一致 | 无需改 |
| D04 | §6.2 | 仍满足 **50 mm 下限** | `03_effect_E2.json expectations.applied_min_clearance_m_gte:true`；`evolution/experience/test_continual_chain.py:137` `assert probe["applied_min_clearance_m"] >= 0.05`；`verify_result.json checks.applied_clearance_at_least_50mm:true` | 0.05 m 下限，实测 0.0814 > 0.05 | 一致 | 无需改 |
| D05 | §6.2 | "**同一份**归档计划、同一条落点间距教训，投给两个消费模块" | `03_effect_E1.json` 与 `03_effect_E2.json` | 两者 `fixture:"t13_two_boxes_one_bin"`、`baseline_sha:"0ae97180f0d2af48"` 完全相同 | 一致 | 无需改 |
| D06 | §6.2 | 投给规划器 **NO_CHANGE**；投给执行器 **CHANGED** | `03_effect_E1.json`（consumer `spread_policy`、verdict `NO_CHANGE`、applied_sha 同 baseline）；`03_effect_E2.json`（consumer `executor_recovery`、verdict `CHANGED`）；`verify_result.json measured.deliveries = {E1:"NO_CHANGE", E2:"CHANGED", E3:"IMPROVED", auto-harness:"CHANGED"}` | 两个判定都成立 | 一致 | 建议补一句：归档里"规划侧"的消费者名是 `spread_policy`（规划器内的落点分配策略），不是 `planner` 本身 |
| D07 | §6.3、摘要、结论、RQ4 | **109** 个实例修 **7** 个，命中率 **6.4%** | `09b_reuse_audit.json`：`instances_offered:109`、`total_instances_fixed:7`、`instance_hit_rate:0.0642`、`total_made_worse:0` | 109 / 7 / 6.42% | 一致 | 无需改 |
| D08 | §6.3、摘要 | **294** 份计划文件改 **7** 份，**2.4%** | `SUMMARY.json` reuse_audit 步：`plans_offered:294`、`plans_correctly_untouched:287` → 改动 7；7/294 = **2.381%** | 294 / 7 / 2.38%（≈2.4%） | 一致 | 可写成 "7/294 = 2.4%"，并注明分母是计划文件（与 D07 的实例分母不可互换，论文已声明） |
| D09 | §6.3 | "没有任何实例被改差" | `09b_reuse_audit.json total_made_worse:0`；`verify_result.json checks.the_skill_made_no_task_worse:true` | 0 | 一致 | 无需改 |
| D10 | §6.4 | "**九个**此类探针逐一执行，任一探针未被覆盖即整门拒绝" | `evolution/experience/demo_continual.py`（`_PLANNER_PROBES` 4 条 + `_EXECUTOR_PROBES` 4 条 + order 1 条 = 9 条声明）；`records_v2.jsonl`（E1 spread_policy `verdict:REJECT`、**无 misuse_check**；E2 probed **4**；order probed **1**；harness probed **2**） | 声明 9 条（spread 4 + respread 4 + order 1）；**归档中实际执行并记录 7 条**（2+4+1，E1 在审核阶段被 REJECT，未进入启用门）；项目自己的报告写 "**8 个探针**覆盖落点/重排/harness 三类"（`docs/EVOBOT_CONTINUAL_CHAIN_20261118.md:1434`） | **不一致**（把"声明数"写成了"执行数"） | 改为："三条条目共声明**九**条失效条件，其中启用门实际执行并记录**七**条探针（spread 条目在审核阶段被拒，未进入启用门）；探针实现共**八**个" |
| D11 | §6.6、结论 | 验收脚本断言 **163** 项检查，不读汇总自述 | `779251f5:setup/acceptance/evobot_continual_chain_20261118/verify_result.json`：`checks_total:163, checks_passed:163`（`checks` 字典恰 163 键，162 个 `true` + 1 个 `[true, "…"]` 复合项） | 163 / 163 | 一致 | 无需改 |
| D12 | §6.5、§6.6、摘要、结论、RQ4 | 目标点名的**四条路由两条送达**（抓放恢复→执行器、操作顺序→规划器；spread 与 ROS launch 为空路由） | `10b_routing_coverage.json`：`named:4, carried:2`；routings = order(planner) **CARRIED by E3**、recovery(executor_recovery) **CARRIED by E2**、spread(spread_policy) **NO_ENTRY**、ROS launch(development) **NO_ENTRY** | 4 / 2，且失败两条状态是 `NO_ENTRY`（路径在、无 ACTIVE 条目），不是 `NO_DELIVERY` | 一致 | 可补：`NO_ENTRY` ≠ `NO_DELIVERY`，论文"空路由"一词建议与归档术语对齐 |
| D13 | §7.2 末段 | 两段锚定不同快照：配置修复固定 `ebe27f07`，经验链固定 `779251f5` 的 `evolution/experience` | `ebe27f07`（无 `evolution/`）；`779251f5`（有 `evolution/experience` 80 文件 + `setup/acceptance/evobot_continual_chain_20261118/` 52 文件） | 两处内容各自确实存在，与"不同快照"的陈述相符 | 一致 | 无需改 |
| D14 | §7.2 末句 | "两处证据均可独立核查" | `git branch -a --contains 779251f5` → 空；`git for-each-ref --contains 779251f5` → 空；`git rev-list --all` 不含 779251f5；`git log --all -- docs/EVOBOT_CONTINUAL_CHAIN_20261118.md` → 空；`ebe27f07` 是 `origin/main` 祖先（可定位） | `ebe27f07` 可核查；`779251f5` 在本克隆为**悬空提交**，经验链归档不在任何可达分支（GitHub 端是否仍可访问：本机无网络核验，未测） | **无法判定** | 把经验链快照挪到一个分支（或把验收包提交到 `main`），并把文献[24]链接改成分支+路径；同时说明"该提交为定点快照，非分支头" |
| E01 | §7.1 | 主试验九份 `result.json` 在 Git 中使用 **LF** | `runs/p1.5-w5e2d-20261109/rep{1..6}/result.json`、`runs/p1.5-w5e2e-20261109/rep{1,2,3-flash}/result.json` | 9/9 文件不含 `\r\n`（各 66 个 LF）；`.gitattributes` 亦为 `* text=auto eol=lf` + `*.json text eol=lf` | 一致 | 无需改 |
| E02 | §7.1 | 历史摘要对应 **CRLF**；直接 SHA-256 不同，按 CRLF 表达后与历史摘要相符 | `aggregate.json` 的 `rows[].sha` + 各 `result.json` 原始字节 | 12/12 条（E2b 3 + E2d 6 + E2e 3）满足：raw LF 哈希 ≠ 记录值、CRLF 归一哈希 **= 记录值**（例 rep1：raw `150dfc1d…`，CRLF `655de595…` = aggregate `sha`） | 一致 | 无需改（这是本稿最扎实的一段） |
| E03 | §7.1 | "本版**分别记录两种摘要**" | 全仓检索：`aggregate.json`/`runs/*/verify.py` 只登记 CRLF 形式摘要；`git grep` 未找到任何 LF 形式摘要（如 `150dfc1d`、`44df1675`）的记录 | 只记录了一种（CRLF）；LF 摘要无落盘，只存在于本次审计的临时计算里 | **不一致** | 要么补一份 `docs/RESULT_DIGESTS.md`（每份 result.json 列 LF/CRLF 两个 sha256 + 转换规则），要么把这句改成"本文只记录历史 CRLF 摘要，LF 原件按 Git blob 存储" |
| E04 | §7.1 | "随文保留逐条数据、统计脚本与文件来源，**支持重算表格**" | `runs/p1.5-w5e2b-20261109/verify.py`、`…w5e2d…/verify.py`、`…w5e2e…/verify.py` | 三个脚本在本检出上**全部失败**：`AssertionError: rep1 drifted`（exit 1）——它们把 `aggregate.json` 的 CRLF 摘要当作 `hashlib.sha256(open(result.json,'rb'))` 的期望值（如 `w5e2d/verify.py:22`） | **不一致** | 二选一：(a) 把 `verify.py` 改成先做 `b.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")` 再比对；(b) 论文改写为"随文保留逐条数据与来源，重算脚本需按 CRLF 归一后比对（现版脚本直接比对原始字节，会失败）" |
| E05 | §7.1、全部 [8]-[19] 链接 | 源码快照 `ebe27f07881200ab0fc74dfaa5490208023bf9d9` 可解析 | `git cat-file -t ebe27f07…` = commit；`git merge-base --is-ancestor ebe27f07 origin/main` = 0 | 可解析，且是 `origin/main` 祖先；论文引用的 5 个 aggregate、manifest、两份预注册、runner/hash_guard/w5e2/agent_fc 在该提交中全部存在（`cat-file` 均为 blob） | 一致 | 无需改 |
| E06 | §7.1、[24] | 经验链快照 `779251f5e307e826213adbb8ad1075a130c293ef` 可解析 | `git cat-file -t 779251f5…` = commit；`git ls-tree -r 779251f5 -- evolution` = 80 文件；`-- setup/acceptance` 有链路包 | 对象存在、可完整解析（悬空，见 D14） | 一致（可解析）；可达性见 D14 | 无需改 |
| E07 | §3.1 | 三门场景集合 `S={dual_object, normal, regrasp}` | `pilot/w5e2.py ACCEPT_C`（`run("dual_object")`、`run("normal")`、`run("regrasp")`，`all(status=="PASS")`） | 三场景名与集合逐字一致 | 一致 | 无需改 |
| E08 | §3.1 | 双门条件只含前两项 | `w5e2.py ACCEPT`（`target=run("dual_object")`、`regression=run("normal")`） | 双门 = dual_object + normal，无 regrasp | 一致 | 无需改 |
| E09 | §3.1 式(1) | 接受需 `J(c)=0`（验收程序退出码） | `w5e2.py` 两个 ACCEPT 脚本均 `sys.exit(0 if passed else 1)`；`pilot/judge.py:39` `verdict["passed"] = bool(verdict.get("passed")) and proc.returncode == 0`；`pilot/runner.py:149` `success = verdict.passed and violation is None` | 退出码门与场景门按"与"合成，与式(1) 同构（且退出码门是冗余加固） | 一致 | 无需改 |
| E10 | §3.1 | 保护通过"工具写入拒绝 + 运行结束后文件摘要复核"实现 | `pilot/hash_guard.py`（`snapshot/verify`，变更即 `ProtectedViolation`）；`pilot/toolbox.py:52,63`（受保护路径写 `REFUSED_PROTECTED`）；`pilot/runner.py:128-136`（violation 使 success=False，即便 verdict 通过也重判） | 双机制齐备，与论文描述一致 | 一致（需补：W5E2 各运行实际传入 `protected=["gate/acceptance.py"]` 单文件，`run_pilot.py:260,286,313,340,371`；manifest 里的 4 文件保护集未用于这 17 条） | 在 §3.1 注明"这 17 条运行的 `P={gate/acceptance.py}`"，否则读者以 manifest 的 `protected` 为准会误判 `P` |
| E11 | §7.1 | 17 条记录来自同一归档日期 **2026-11-09** | 五个目录名均以 `-20261109` 结尾；`manifest.json` `revised_at:"2026-11-09"` | 命中 | 一致 | 无需改 |

---

## 最严重的 3 处不一致

**① §7.1「分别记录两种摘要」+「统计脚本支持重算」同时不成立（E03 + E04，可复现失败）**
仓库只登记了 CRLF 形式摘要（`aggregate.json rows[].sha`、三个 `runs/*/verify.py` 里的常量），没有任何 LF 摘要落盘；而三个随文脚本把"原始字节的 sha256"和"CRLF 形式摘要"直接比，因此在按 `.gitattributes` 归一为 LF 的检出上**必然失败**：

```
python experiments/pilot-001/runs/p1.5-w5e2d-20261109/verify.py
  AssertionError: rep1 drifted   (verify.py:22)   exit=1
python experiments/pilot-001/runs/p1.5-w5e2b-20261109/verify.py   -> rep1 drifted  exit=1
python experiments/pilot-001/runs/p1.5-w5e2e-20261109/verify.py   -> rep1 drifted  exit=1
```

这是全稿唯一"读者照做必然踩空"的地方：论文的诚实断言（"未将换行转换写作原始字节校验通过"）是对的，但配套的"重算脚本"与"两种摘要记录"两项承诺在归档里没有落地。

**② §6.4「九个此类探针逐一执行」（D10，把声明数写成了执行数）**
归档里 `records_v2.jsonl` 的 `misuse_check.probed` 合计 **7**（harness 2 + executor_recovery 4 + planner 1）；spread 条目（E1）在审核阶段被判 `REJECT`，其 4 条声明**从未进入启用门**，因此"逐一执行"不成立。项目自己的报告更把它写成"8 个探针覆盖三类消费者"。同一件事在三个地方用了三个数（9 声明 / 8 实现 / 7 执行），审稿人只需打开一个 JSON 就能发现。

**③ §7.2「两处证据均可独立核查」（D14，经验链快照在本克隆中不可由任何分支定位）**
`779251f5` 能 `cat-file`，但 `branch -a --contains`、`for-each-ref --contains`、`rev-list --all` 全为空；`docs/EVOBOT_CONTINUAL_CHAIN_20261118.md` 与整个 `setup/acceptance/evobot_continual_chain_20261118/` 归档包也只在该悬空提交里（`git log --all -- <path>` 为空）。第 6 章每个数字我都核到了，但读者**没有路径**走到它们：只能按哈希 `git show`，在 GitHub 上是否仍可访问本机无法验证。

（其余不一致均已在表中给出可执行改法；另有 1 条"需补注"类观察：C01 的 E2 aggregate 自述上限 ≤3 与 manifest/记录的 4 轮冲突 —— 论文按 4 轮写是对的，但建议在脚注中主动交代这个归档内部矛盾。）

---

## 建议论文改哪几句（可直接替换）

1. §6.4 第 149 行整句改为：
   > "启用前的第三类检查针对不适用场景：若指令并未固定顺序、目标间距已满足契约、或落点本就只有一个阶段，规则必须保持沉默。三条条目共声明九条此类失效条件；启用门实际执行并记录了七条探针（落点间距条目在审核阶段被拒，未进入启用门），任一已声明条件无对应探针即整门拒绝，不以未观察到误用代替检查。探针实现共八个。"
2. §7.1 第 169 行改为两句：
   > "本版保留 LF 原件，并按历史 CRLF 形式复核摘要：12 份 `result.json`（含 E2b 三条）的原始字节 SHA-256 与归档记录不同，按 CRLF 归一后逐条与归档摘要相符。随文三个 `runs/*/verify.py` 目前直接比对原始字节，需先做 CRLF 归一才能在 LF 检出上复算；两种摘要的对照表见 `docs/RESULT_DIGESTS.md`。"
   （若不想补对照表，则删掉"分别记录两种摘要"，只保留"只记录 CRLF 形式摘要"。）
3. §7.2 第 183 行改为：
   > "本文两段工作锚定不同的源码快照：配置修复固定于 `ebe27f07`（`origin/main` 祖先，可直接定位）；经验链固定于 `779251f5` 的 `evolution/experience` 与 `setup/acceptance/evobot_continual_chain_20261118/`，该提交为定点快照而非分支头，需按哈希取用；`evolution/` 在 `ebe27f07` 中不存在。"
4. §4.1 表头与 §3.1 各加一处注：
   - 表头把 "normal / regrasp" 改成 "regression_normal / regression_regrasp（aggregate 记作 normal、regrasp）"；
   - §3.1 第 53 行后补："这 17 条运行的受保护文件集合为 `P={gate/acceptance.py}`。"
5. §4 表 E2 行后加脚注："E2 的 aggregate 自述上限为 ≤3 轮，而其 manifest 上限与实际记录均为 4 轮；本文按 manifest 与记录记 4 轮。"

## 复现方式（全部只读）

```powershell
# 1) 17 条记录、逐条 iters/tokens/verdict
python - <<'PY'
import json,glob,os
R=r"…\wt-grasp-probe\experiments\pilot-001\runs"
for d in ["p1.5-w5e2-20261109","p1.5-w5e2b-20261109","p1.5-w5e2c-20261109","p1.5-w5e2d-20261109","p1.5-w5e2e-20261109"]:
    for f in sorted(glob.glob(os.path.join(R,d,"**","*result.json"),recursive=True)):
        j=json.load(open(f,encoding="utf-8")); print(f, j["iterations"], j["cost"]["tokens"], j["success"])
PY

# 2) 摘要口径（raw vs CRLF）
python - <<'PY'
import hashlib
b=open(r"…\runs\p1.5-w5e2d-20261109\rep1\result.json","rb").read()
print(hashlib.sha256(b).hexdigest())                                   # 150dfc1d…（LF）
print(hashlib.sha256(b.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")).hexdigest())  # 655de595…（= aggregate sha）
PY

# 3) 第 6 章归档（悬空提交，按哈希取）
git -C …\wt-grasp-probe show 779251f5:setup/acceptance/evobot_continual_chain_20261118/03_effect_E2.json
git -C …\wt-grasp-probe show 779251f5:setup/acceptance/evobot_continual_chain_20261118/verify_result.json
git -C …\wt-grasp-probe show 779251f5:setup/acceptance/evobot_continual_chain_20261118/10b_routing_coverage.json
git -C …\wt-grasp-probe branch -a --contains 779251f5   # 空 = 悬空

# 4) 随文脚本现状（预期失败）
python …\runs\p1.5-w5e2d-20261109\verify.py   # AssertionError: rep1 drifted, exit 1
```

机器可读版本：`docs/PAPER_V02_AUDIT.json`（55 条 `{claim_id, paper_value, evidence_path, measured, verdict}`）。
