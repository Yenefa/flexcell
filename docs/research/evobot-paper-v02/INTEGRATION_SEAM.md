# #249 与 #250 的接缝：适配器契约（给 #252）

> **状态：DRAFT。离线验证，合成夹具。**
> 两个模块各自的测试都通过，但它们**没有一起跑过**。#252 要做的第一件事就是把它们接起来。
> 本文件记录接缝实测的结果与必须补的东西。

## 1. 实测（2026-11-16）

用 #250 语料里的真实 P1 用例当测量报告，喂给 #249 的边界：

`
{
  "identity": {
    "policy_id": "flexcell.repair_eval.visibility/2026-11-16-issue249",
    "policy_fingerprint": "0dd92501d00855c9e187865a6c75fe02f1b38e5be8298bcf37cd4d6f1e2e6769",
    "condition": "A_STATIC",
    "feedback_source": "none"
  },
  "a_reads_verdict": "reserved_name",
  "a_reads_candidate_source": "allowed",
  "freshness": "stale_artifact",
  "contract_sha256": "4720f40fd8a1c6616fb64285a419628d0a1fd18ec6933e14f705f2560c97d3f5",
  "p1_status": "ACCEPT",
  "claim_flip": {
    "status_unchanged": true,
    "codes_unchanged": true,
    "claim_recorded_somewhere": true,
    "dict_differs": true
  },
  "goal_missed_but_claims_success": {"status": "REJECT", "codes": ["GOAL_NOT_MET"]}
}
`

四条结论：

1. A 条件读 `verdict.json" 被拒（`reserved_name`），读候选源码被允许——**拒绝是机制，不是提示**。
2. 候选目录有残留裁决时 `assert_fresh_run` 抛 `stale_artifact`（fail-closed，新运行不继承旧反馈）。
3. 把 `claim_success` 从 false 翻成 true：`status` 与 `codes` **都不变**（仍是 `ACCEPT`），差异只出现在被记录的字段里——这正是设计要的"记录但不采信"。
4. 把目标改到容差外再声称成功：`REJECT / GOAL_NOT_MET`——自述不能救回一个没达成的目标。

## 2. 缺口：没有转换层

| 边界给出 | 契约需要 | 现状 |
| --- | --- | --- |
| `ToolFacade` 的受限读取 + `FeedbackPacket` + `RunBoundary.describe()` | 一份候选测量报告（dict，`flexcell.repair_eval.candidate/1`） | **没有代码把前者变成后者** |

#252 要写的适配器至少要做三件事：

1. **新鲜度先于读取**：先 `assert_fresh_run`，失败就停（不能让一次运行继承上一次的产物）。
2. **反馈按条件取**：#249 的 `FeedbackPacket` 已经是 A=None / B=own_run / C=mismatch_run+flag / D=own_run+guidance，直接路由，不要重新实现。
3. **身份随记录落盘**：每条 run record 必须同时写 `policy_id`、`policy_fingerprint`、`condition`、`contract.sha256()`、`contract.version`。缺一项，事后无法证明"这一轮用的是哪版规则"。

## 3. 一个仍然存在的限制

适配器只能保证"规则一致"，不能保证"测量真实"：`evaluate()` 信任 `candidate_state` 里的位置/哈希/退出码，
而谁能写这些值由 #249 的边界约束。**两层必须一起用**，单独用任一层都不足以防住"改测量值"或"偷看裁决"。

## 4. 复核命令（离线、无模型）

`
python3 tools/recompute_w5_archive.py --runs experiments/pilot-001/runs   # 历史数字重算
python3 -m pytest benchmark/repair_eval -q                               # #249 的边界用例
python3 -m pytest benchmark/repair_eval/contracts -q                     # #250 的契约用例
`

接缝探针脚本没有进仓库：它依赖两个尚未合并的分支，放进任一分支都会指向另一条分支上不存在的代码。

> **2026-11-16 已落地。** #262（`codex/evobot-paper-v02-control-runs`）把 #249、#250、#251 三条分支合到一起，
> 探针随之变成用例 **`experiments/repair_eval_v02/test_seam.py`**（7 条，3 个变异全部 KILLED）。
> 文件没有放在本文件原先建议的 `benchmark/repair_eval/test_seam.py`，原因是那属于 #249 的分支；
> 接缝测试要同时依赖两层，放在已经合并三层的那条分支上才成立。
>
> 另补了两条探针当时没覆盖的身份断言：一条记录必须能同时写下 `policy_id` 与 `contract.sha256()`；
> **策略内容一改，`fingerprint` 必须随之改变**——否则「记录了指纹」证明不了任何事，
> 规则可以在名字不动的情况下被换掉。这一条是这次复核时才想明白的。

