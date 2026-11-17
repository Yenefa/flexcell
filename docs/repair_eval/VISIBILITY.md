# 修复评测的信息可见性边界（issue #249）

父任务 #248（论文 v0.2）。本模块只做一件事：让"无反馈条件看不到裁决"从口头约定
变成可执行、可回归的检查。它不评价模型能力，不产生机器人 PASS/FAIL，也不改冻结的
评估器、阈值或历史证据。

## 1. 要解决的泄漏点

- `experiments/pilot-001/pilot/toolbox.py` 按**工具名**授权（`ToolBox(allowed=...)`），
  路径只做 `startswith` 检查；
- `experiments/pilot-001/pilot/w5.py:178` 把 `verdict.json` 写进候选 workspace；
- 因此 A（无反馈）条件只要调用 `read_file("verdict.json")` 就能读到独立裁决，
  条件标签只是社会学约定，不是结构约束。

本模块把"候选工作副本 / 独立裁决 / 隐藏材料"拆成互不重叠的目录根，用版本化策略
决定每个条件能看到哪一类材料，并把每次读/写/列目录的判定记进 `attempts`。

## 2. 文件与边界

| 文件 | 作用 |
|---|---|
| `benchmark/repair_eval/visibility.py` | 策略加载、目录边界、工具门面、反馈包、demo/审计 CLI；纯标准库 |
| `benchmark/repair_eval/visibility_policy.json` | 版本化策略（`schema_version` + 条件表 + 受保护写入清单 + 诊断投影） |
| `benchmark/repair_eval/test_visibility.py` | 离线负例/正例回归（pytest，61 项） |
| `docs/repair_eval/VISIBILITY.md` | 本文：条件表、理由码、负例清单、已知限制、集成注意点 |

本 issue 的写入范围只有 `benchmark/repair_eval/` 和 `docs/repair_eval/`。
`experiments/pilot-001/pilot/`（含 w5.py、toolbox.py、judge.py）**未改动**，接线见第 8 节。

## 3. 目录边界

一次运行有三个必需根，全部 `resolve()` 规范化，构造时即校验互不包含：

```
<run_root>/
  candidate/       候选工作副本：
                    静态输入  task.md, tests/    （四条件均可读）
                    sealed    gate/              （四条件均不可读；留在盘上只为子进程能跑）
                    候选源码  skill/ 等          （可读、可写）
  verdict/         独立裁决：verdict.json（agent 侧只有 verification 类别可达，本策略全 false）
  hidden/          隐藏答案：hidden_answer 类别，本策略全 false
<另一条已完成 run>/  mismatch 源：telemetry/execution.log + verdict.json，仅 C 条件可达
```

构造期拒绝（`PolicyError`）：根不存在、`candidate/verdict/hidden` 不在 `run_root` 内、
任意两根互相包含、`mismatch` 与三者任一重叠。原因码 `root_overlap`。

## 4. 条件 → 可见性表

`visibility_policy.json` 是唯一事实来源（下表由它生成，测试断言二者一致）。

| 条件 | 静态输入 | 候选源码 | 执行反馈 | 诊断 | 独立裁决 | 隐藏答案 | 反馈来源 | 指导文本 |
|---|---|---|---|---|---|---|---|---|
| `A_STATIC` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | `none` | ❌ |
| `B_REAL_FEEDBACK` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | `own_run` | ❌ |
| `C_MISMATCHED_FEEDBACK` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | `mismatch_run` | ❌ |
| `D_GUIDED` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | `own_run` | ✅（策略内声明，≤1200 字符） |

`gate/` 不属于上表的任何一类：它是**封印材料**（`sealed_prefixes`），四个条件一致不可读，
因此不参与条件间差异。`tests/` 是回归定义，四个条件一致可读，同样不参与差异。

设计取舍：

- **`gate/` 四条件封印**（2026-11-16 修订，见第 6.2 节）：验收命令与阈值就是"尺子"。
  读到 `PASS_IF = {"max_error": 0.02}` 的修复者可以照着阈值调参而不是修好任务，所以
  `gate/` 在 A/B/C/D 下一律 `sealed_material`。它仍物理留在候选目录里，因为验收子进程
  要在那里运行——封印是**工具门面**的属性，不是文件系统属性。
- `tests/` 保持可读：它是"不许弄坏什么"的回归定义，不含验收阈值；封掉它会让修复者看不见
  自己必须保住的契约。四条件一致可见，因此不引入组间差异。
- `verification`（裁决原文）和 `hidden_answer` 在**所有**条件下为 false，加载器强制
  `hidden_answer` 永不可见，并强制 `A_STATIC` 的 feedback/diagnosis/verification/hidden
  全 false；写了 `feedback_source` 却不开放 `execution_feedback`（或反之）直接拒绝。
- `diagnosis` 是**本次运行自己的反馈**的有界结构化投影（source = `telemetry/execution.log`），
  不是裁决的二次投影——所以 B/C/D 拿到它不等于看到测量结果。投影键由策略
  `diagnosis.projection` 决定，`truncate_chars` 截断；裁决根只有 `verification` 通道。
- C 与 B 的**可见类别集合相同**，差别只在内容来源与 `mismatched=true` + 来源 run id：
  这样 C 控制的是"信息内容"而不是"信息形态/数量"。
- `A_STATIC` 的 `FeedbackPacket` 是 `None`（不是空字符串），避免"无反馈"被误当成
  "空反馈"参与统计。
- 加载器要求至多一个条件携带 `guidance`（否则两个条件等于同一个干预），并校验指导文本
  只能附加在 `own_run` 的真实反馈上。

## 5. 拒绝理由码

`attempts` 里每条判定都有 `decision`（allow / deny / note）与 `reason`（deny/note 时）：

| 理由码 | 触发条件 | 对应负例 |
|---|---|---|
| `policy_denied` | 当前条件不开放该类别（如 A 调 `read_telemetry`/`read_diagnosis`/`read_verification`，或 A 读 `telemetry/...`） | `test_a_telemetry_and_diagnosis_tools_are_refused` |
| `reserved_name` | 文件类别请求命中 `reserved_names`（`verdict.json`、`result.json`、`judge_verdict.json`、`hidden_answer.txt`） | `test_a_read_verdict_json_is_refused` |
| `absolute_path` | 绝对路径 / 盘符前缀 / UNC 前缀 | `test_a_read_of_an_absolute_path_is_refused` |
| `parent_traversal` | 任一路径段为 `..`（在解析前拒绝，故 `../<另一个 run>/verdict.json` 报此码） | `test_a_read_of_a_sibling_run_is_refused` |
| `symlink_alias` | 词法上在允许根内、`resolve()` 后落到根外（含指向 verdict/hidden 的别名） | `test_a_read_through_a_symlink_alias_is_refused` |
| `outside_root` | 规范化后仍在根外（含 NUL 字节） | `test_write_outside_the_candidate_is_refused` |
| `verdict_material` | 解析结果落入裁决根（非 verification 类别的纵深防御） | — |
| `hidden_material` | 解析结果落入隐藏材料根 | — |
| `hardlink_alias` | 文件 `st_nlink>1` 且在裁决/隐藏/mismatch 根内找到同 `(st_dev, st_ino)` | `test_a_cross_root_hard_link_is_refused` |
| `hardlink_unverified` | `st_nlink>1` 但有界扫描未发现跨根同 inode：记 note，不拒绝（见限制） | — |
| `sealed_material` | 请求命中 `sealed_prefixes`（当前为 `gate/`），四个条件一致拒绝 | `test_the_evaluator_source_is_sealed_in_every_condition` |
| `protected_write` | 写入命中 `protected_writes`（`task.md`、`gate/`、`tests/test_regression.py`、`verdict.json`、`result.json`、`telemetry/`、`experience/`、`diagnosis.json`） | `test_protected_writes_are_refused` |
| `stale_artifact` | `assert_fresh_run` 在候选目录发现上一轮残留（`verdict.json`、`result.json`、`evidence.json`、`episode.json`、`fingerprint.json`、`diagnosis.json`、`telemetry/`、`experience/` 等） | `test_stale_candidate_is_refused` |
| `root_overlap` | 构造期根目录重叠 | `test_overlapping_roots_are_rejected` |
| `missing_material` | 允许读但文件不存在（`MaterialUnavailable`，不是拒绝） | — |

路径判定顺序固定：**策略类别 → 路径形状（绝对/`..`）→ 内容根包含 → 保留名 → 封印根 →
硬链接**。所以 `../run-a/verdict.json` 报 `parent_traversal` 而不是 `reserved_name`。

## 6. 已验证的负例清单

```bash
cd /home/ros/wt/visibility
python3 -m pytest benchmark/repair_eval/test_visibility.py -q
```

当前结果：`61 passed`。负例与正例（测试名可检索）：

- **A 读不到裁决**：`test_a_read_verdict_json_is_refused`（`reserved_name`）；
  `test_a_telemetry_and_diagnosis_tools_are_refused`（三个反馈工具 + 经 `read_file` 读
  `telemetry/` 全被 `policy_denied` 拒绝）。
- **A 读不到相邻 run**：`test_a_read_of_a_sibling_run_is_refused`（`../run-a/verdict.json`
  与 `skill/../../run-a/verdict.json` 均为 `parent_traversal`）。
- **A 走别名拿不到裁决**：`test_a_read_through_a_symlink_alias_is_refused`、
  `test_a_symlink_to_hidden_material_is_refused`（`symlink_alias`）；
  `test_a_cross_root_hard_link_is_refused`（`hardlink_alias`）。
- **别名不是一次校验就作数**：`test_a_read_through_a_repointed_symlink_is_still_refused`
  ——先让同名软链 `swap.txt` 指向候选内允许文件并成功读一次，再把软链换成
  `../verdict/verdict.json`（以及 `../hidden/answers.txt`）重读，仍是
  `symlink_alias`，且拒绝记录落在 `swap.txt` 上。这条断言的是"每次读都按
  当前真实路径判定"，而不是"校验那一刻解析过一次"。
- **策略加载即失败**：`test_policy_loading_fails_closed_instead_of_silently_allowing`
  （把 A 的 `verification` 改成 true → 加载直接 `PolicyError`，没有构造出 Policy
  对象）；而同样的放宽施加在**已加载**对象上时，门面会照策略执行
  （`test_verification_access_is_policy_driven`）——所以兜底的是加载器，不是读取时的运气。
- **A 的反馈是 None**：`test_no_feedback_is_none_not_an_empty_string`。
- **B 反馈带真实来源与摘要**：`test_b_feedback_packet_carries_its_own_source_and_digest`
  （`source_run_id=run-b`、`source_root=candidate`、`sha256 == sha256(log)`、`mismatched=False`）。
- **C 标 mismatched 且来自另一条固定 run**：`test_c_feedback_is_the_fixed_other_run_and_is_tagged`
  （`source_run_id=run-a`、`source_root=mismatch`、`mismatched=True`、与 B 的摘要不同）；
  `test_c_without_a_mismatch_run_fails_closed`（缺 mismatch 根或来源 run id 直接报错）。
- **D 含显式指导且受策略约束**：`test_d_adds_bounded_guidance_on_top_of_real_feedback`
  （指导文本 == 策略原文、长度 ≤ `guidance_max_chars`、`guidance_sha256` 可复核、包里不含
  任何封印材料）、`test_only_the_guided_condition_carries_guidance`。
- **不继承旧反馈**：`test_stale_candidate_is_refused`（候选目录里旧的 `verdict.json`、
  `telemetry/`、`experience/` 全部列出并拒绝）、`test_module_level_freshness_check_matches_the_boundary`；
  正例 `test_fresh_candidate_passes`、`test_freshness_does_not_count_frozen_static_input`。
- **允许路径**：`test_a_reads_static_input_and_candidate_source`（`task.md`、`skill/`、
  `tests/test_regression.py`、`list_dir`、`search_code` 均可用，且读后输入文件未被改写）。
- **写受保护清单被拒**：`test_protected_writes_are_refused`（写后原文不变）、
  `test_candidate_source_write_is_allowed`（只允许写候选源码）。
- **A 与 B 可见集合不同（策略断言，不靠人工）**：`test_a_and_b_visible_sets_differ`
  （`A ⊂ B` 且差集恰为 `{execution_feedback, diagnosis}`），并有行为层对照
  `test_the_same_tree_exposes_different_material_under_a_and_b`（同一棵树：A 调 `read_telemetry`
  被拒、B 返回真实日志；两者 `read_verification` 都被拒）。
- **验收门四条件封印**：`test_the_evaluator_source_is_sealed_in_every_condition`
  （A/B/C/D 读 `gate/acceptance.py`、`gate/sim.py` 全部 `sealed_material`，并核对拒绝记录里的
  condition）、`test_sealed_material_is_not_reachable_by_listing_or_search`
  （`list_dir("gate")` 被拒、`search_code("PASS_IF")` 返回 `(no matches)`）、
  `test_writing_the_sealed_gate_is_still_refused`（写仍是 `protected_write`，原文不变）。
- **封印不阻断执行**：`test_sealed_files_still_exist_for_the_gate_subprocess`——门面拒读的同时，
  普通子进程仍能执行 `gate/acceptance.py` 并拿到输出，说明封印只约束 agent 的读取通道。
- **回归定义保持可读**：`test_the_regression_definition_stays_readable_in_every_condition`。
- **分类不串味**：`test_categories_put_the_gate_and_the_regression_definition_apart`
  （`task.md`/`tests/` → `static_input`，`gate/` 非静态，`telemetry/` → `execution_feedback`）。
- **策略本身可拒绝**：`test_loader_refuses_a_policy_that_breaks_the_design`（15 个用例：
  A 开放反馈/诊断、来源与可见性不一致、缺条件、多条件、错版本、指导文本越界、指导挂在
  mismatched 上、两个条件都带指导、hidden 可见、freshness 漏保留名、保留名带路径、绝对
  策略路径、未知顶层键、visible 缺类别）。
- **门面是策略驱动而非硬编码**：`test_verification_access_is_policy_driven`——只放宽内存里的
  policy 对象，`read_verification` 就返回裁决文本；说明拒绝来自策略，而不是代码写死。
  出厂策略没有任何条件开启它（`test_every_condition_keeps_the_verdict_and_hidden_answers_sealed`）。
- **搜索不穿透**：`test_search_does_not_reach_the_verdict_or_hidden_material`（`LEAK_MARKER`
  在裁决与隐藏答案里，搜索返回 `(no matches)`）。
- **行为记录**：`test_attempts_record_every_decision_with_a_reason_code`（allow/deny 都记，
  理由码在 `REASON_CODES` 内）。

### 对抗性复核记录（2026-11-16，另一名审阅者）

方法：不改代码，按攻击者思路绕过门面，七类绕法共 22 类攻击；判据是"能否读到
sealed 材料"。结果：**无一类读到**，全部落在上表的理由码上。

| 攻击 | 结果 |
|---|---|
| 直接读 `verdict.json`（对照） | `reserved_name` |
| `./verdict.json`、`skill//../verdict.json` | `reserved_name` / `parent_traversal` |
| 大小写折叠 `VERDICT.JSON`、尾点、尾空格 | `missing_material`（精确名字匹配，解析后不同名即取不到；见第 9 节平台说明） |
| 嵌套 `..`、`../verdicts/verdict.json`、绝对路径 | `parent_traversal` / `absolute_path` |
| 候选内部建符号链接指向 sealed 文件 | `symlink_alias` |
| 候选内部建目录软链指向 sealed 目录 | `symlink_alias` |
| 先读一次再重定向软链（TOCTOU 式） | `symlink_alias`（重定向后仍拒绝） |
| A 调 `read_feedback` / `diagnose` / `read_verification` | `policy_denied` |
| `list_entries` 是否泄漏 sealed 名字 | 不泄漏 |
| 写 `task.md`、写 `verdict.json` | `protected_write` |
| 把策略改成 A 可见 `verification` 再加载 | `PolicyError`（加载期自校验） |

这些探针刻意没有全部改名成正式用例：多数与第 6 节已有断言重复，重复计数会稀释
"覆盖率"的含义。只有两条原先没有单独断言的性质被补成显式用例——上表的
"软链重定向"（`test_a_read_through_a_repointed_symlink_is_still_refused`）和
"策略加载期自校验"（`test_policy_loading_fails_closed_instead_of_silently_allowing`），
两条都做过反向验证：去掉对应的机制，用例会失败。

### 与 #251 协议文本的交叉核对（2026-11-16，修订）

#251 的 `PROTOCOL.md` §2 写"A 仅获得任务目标文本与允许修改的字段清单"，第 60 行的拒绝列
明确列出"读评估器源码"。而 r1 策略把 `gate/` 放进了 `static_prefixes`，使 A/B/C/D 都能读到
`gate/acceptance.py` 里的 `PASS_IF` 阈值——**两份交付物互相矛盾**。

判断：**改 #249 这一边**，不动协议。理由：

1. 协议那句话是对的：读到阈值就能照尺子调参，这正是契约层要防的"改尺子"；
2. 修复成本低且不改变对照：`gate/` 四条件一致封印，A 与 B 的差仍是"执行反馈 + 诊断"；
3. 反过来改协议（把 `gate/` 写成四条件共同可见）会把可证伪的陈述写进论文——审稿人只要
   发现 A 能读 `PASS_IF`，"A 只拿到任务目标文本"就是假的。

落实（`policy_id` 升到 `...-issue249-r2`）：

- 策略新增 `sealed_prefixes: ["gate/"]`，`static_prefixes` 收窄为 `["task.md", "tests/"]`；
- 加载期校验：sealed 与 static 前缀不得重叠、sealed 必须被 `protected_writes` 覆盖（可读可写
  等于没封）、sealed 不得是整个候选目录；
- 三个读取工具对 sealed 前缀一律 `AccessDenied / sealed_material`；写仍走 `protected_write`；
- 新增 9 条用例（第 6 节），并对"去掉封印""去掉 protected_writes 校验"各做一次变异验证，两次用例都失败。

顺带修掉一个由此暴露的缺陷：前缀规范化把目录前缀写成了 `tests//`、`gate//`，导致
`static_prefixes` 实际上从未匹配成功——r1 里 `task.md`/`tests/` 一直被当作
`candidate_source` 而非 `static_input`（可见性结论未变，但分类是错的）。已改为单斜杠，
并有用例 `test_categories_put_the_gate_and_the_regression_definition_apart` 盯住。

## 7. 可执行检查与允许/拒绝例子

一条命令打印"允许读 / 拒绝读 / 拒绝继承旧反馈"（输出为 JSON，路径均相对临时树，可 diff）：

```bash
cd /home/ros/wt/visibility
python3 -m benchmark.repair_eval.visibility --demo
```

关键输出（节选，本机实际运行）：

```json
{
  "policy": {"policy_id": "flexcell.repair_eval.visibility/2026-11-16-issue249",
             "schema_version": "repair-eval-visibility/1",
             "fingerprint": "a48651c0...f71ea951a"},
  "visibility": {
    "A_STATIC": ["candidate_source", "static_input"],
    "B_REAL_FEEDBACK": ["candidate_source", "diagnosis", "execution_feedback", "static_input"]
  },
  "examples": {
    "allowed_read": {"condition": "A_STATIC", "path": "skill/recovery.py", "bytes": 218,
                     "sha256": "f57512bc...ce93be"},
    "refused_reserved_name": {"path": "verdict.json", "reason": "reserved_name", "refused": true},
    "refused_parent_traversal": {"path": "../run-a/verdict.json", "reason": "parent_traversal"},
    "refused_symlink_alias": {"path": "alias.txt", "reason": "symlink_alias"},
    "refused_feedback_tool": {"tool": "read_telemetry", "reason": "policy_denied"},
    "no_feedback": {"packet": null, "is_none": true},
    "real_feedback": {"packet": {"source_run_id": "run-b", "mismatched": false,
                                 "sha256": "9b6e9e0c...30b1a2"}},
    "mismatched_feedback": {"packet": {"source_run_id": "run-a", "mismatched": true}},
    "guided_feedback": {"guidance_length": 182, "guidance_max_chars": 1200,
                        "within_policy_bound": true},
    "refused_stale_inheritance": {"refused": true,
      "artifacts": ["experience", "telemetry", "verdict.json"]},
    "attempts_recorded": {"denials": 4,
      "reasons": ["parent_traversal", "policy_denied", "reserved_name", "symlink_alias"]}
  }
}
```

审计一条真实运行树（不改任何文件；退出码 0=可继续，1=被拒，2=配置/策略错误）：

```bash
python3 -m benchmark.repair_eval.visibility \
  --condition A_STATIC --run-root runs/run-b \
  --candidate runs/run-b/candidate --verdict runs/run-b/verdict \
  --hidden runs/run-b/hidden --check-freshness --read skill/recovery.py
```

## 8. 集成注意点（未在本 issue 内改动）

1. **接线位置**：`experiments/pilot-001/pilot/runner.py:74` 现在把
   `judge_verdict_path=ws/"verdict.json"` 交给 `ToolBox`。v0.2 路径应改成
   `RunBoundary(policy, run_root, candidate, verdict, hidden, condition=...)` +
   `ToolFacade(boundary)`，并把该 run 的 `condition`、策略指纹、可见类别写进 run record
   （`RunBoundary.describe()` 已给出）。
2. **裁决写入点必须外移**：`w5.py:178`（以及 `judge.py:40` 的 `workspace/verdict.json`）
   要把裁决写到 `verdict/` 根，而不是候选 workspace；否则 `assert_fresh_run` 会在下一轮
   直接 fail-closed。该改动属于 `experiments/`，需 owner 提独立 PR，本 issue 未动。
3. **执行仍发生在候选副本内**：`gate/`、`tests/` 必须留在候选目录里供子进程运行，
   不搬到根外。区别在读取通道：`tests/` 按 `static_prefixes` 归类为静态输入（四条件可读、
   写入受保护），`gate/` 按 `sealed_prefixes` 四条件封印（写入受保护、agent 不可读）。
   门面不参与执行，所以封印不影响子进程——`test_sealed_files_still_exist_for_the_gate_subprocess` 盯这一点。
4. **旧工具的语义差异**：`toolbox.read_verification()` 在 A 臂上以前返回 `None`（文件不存在），
   现在一律 `AccessDenied(policy_denied)`；调用方要按"被拒"处理，不能当成"无内容"。
5. **不替换证据链**：`evidence.py` 的 `REQUIRED` 清单、`hash_guard`、冻结评估器与阈值都不变；
   本模块只决定"谁能读什么"。

## 9. 已知限制（必须随结果一起报告）

- **封印只在门面层**：`gate/` 在四个条件下都不可读，但文件仍在候选目录里、权限未收紧。
  绕过门面的代码（直接 `open()`、shell、子进程）照样能读它——因此"A 看不到评估器源码"
  只能在"通过工具门面访问"这一层陈述，不能写成文件系统级保证。
- **这是路径门，不是运行时沙箱**。它只约束通过 `ToolFacade`/`RunBoundary` 的访问。
  同一用户直接用 shell、`open()`、`/proc/<pid>/root` 或任何绕过门面的代码都能读裁决目录；
  同机 root、容器逃逸、绑定挂载（bind mount）同理。**不能**把"A 条件无反馈"表述为
  "A 条件在物理上不可能获得反馈"。
- **硬链接是尽力检测**：只有当 `st_nlink>1` 且能在裁决/隐藏/mismatch 根（深度 ≤4、
  ≤400 条目）里找到同 `(st_dev, st_ino)` 才拒绝；跨挂载点或超出扫描预算的同 inode
  只记 `hardlink_unverified` 的 note，不拒绝。
- **符号链接只看解析结果**：指向允许根内合法文件的链接是允许的；`list_dir` 会显示链接
  名字（不显示目标内容）。目录符号链接在 `search_code` 中不递归。
- **`..` 一律拒绝**，包括 `skill/../skill/recovery.py` 这类本可规范化的写法；调用方应传
  规范化相对路径。
- **名字匹配区分大小写**：保留名与受保护写入按精确名字比较。在大小写不敏感的文件系统
  （macOS/Windows 默认）上，`VERDICT.JSON` / `GATE/sim.py` 这类写法可能落到真实
  文件上，届时需要额外做大小写折叠比较。本仓库目标平台是 Ubuntu（区分大小写），本次未实现
  该折叠；跨平台移植前必须补上。
- **`assert_fresh_run` 只看名字**：候选目录里叫 `verdict.json`/`result.json`/… 的文件与
  `telemetry/`、`experience/` 目录会被判为残留，即使内容无害；反之改了名的残留不会被发现。
- **诊断投影不是语义脱敏**：它按策略键名单截断，若执行日志本身包含敏感文本，投影仍会带上。
- **未测量项（UNKNOWN）**：模型/工具/提示接口版本在策略里是占位符
  （`model_id`、`prompt_template_version`、`harness_version` 均为 `PLACEHOLDER_UNSET`），
  本 issue 没有运行任何模型或仿真，也没有改变论文的正式基线。

## 10. 版本与变更规则

- `schema_version` = `repair-eval-visibility/1`；不认识的版本加载器直接拒绝。
- 当前 `policy_id` = `flexcell.repair_eval.visibility/2026-11-16-issue249-r2`（r2：`gate/` 转为
  `sealed_prefixes`，`static_prefixes` 收窄；原因见第 6.2 节）。r1 的指纹
  `0dd92501…` 只对应"gate/ 可读"的旧约定，不要与新记录混用。
- 改条件表、保留名、受保护写入清单、诊断投影 = **协议变更**：必须同时改
  `policy_id`、更新本文第 4/5 节与负例清单，并在提交信息里说明原因。
- `RunBoundary.describe()` 里的 `policy_fingerprint`（策略 JSON 的规范化 SHA-256）应与
  每次运行的记录一起保存，便于事后确认"这一轮用的是哪版可见性策略"。
