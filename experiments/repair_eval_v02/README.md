# #252 对照矩阵：机制试运行（DRY RUN）

> **状态：DRY RUN —— 没有任何模型参与，不是能力结果，不得进入任何分母。**
> 本目录证明的是"24 槽矩阵、条件路由、可见性边界、契约判定、新鲜度门能够端到端串起来"，
> 不证明任何关于模型能力的结论。

## 为什么先做这一步

本机**没有模型凭据**，实测三处全部为空：

| 来源 | 结果 |
| --- | --- |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `FLEXCELL_PILOT_API_KEY` | 全部 unset |
| gate 脚本 `/mnt/c/Users/fuker/.../evobot_llm_key.sh` | 路径不存在 |
| `~/.config/flexcell/pilot.env` | 不存在 |
| Windows 注册表 `HKCU` / `HKLM` 的 `FLEXCELL_PILOT_API_KEY` | 均未设置 |

在拿不到 key 的情况下，选择是：把 24 槽标成 NOT_RUN 等授权，或者用仓库自带的 `ScriptedAgent`
把**同一套 24 槽、同一个适配器**跑一遍。选后者，理由是本仓库已经吃过两次同样的教训——
**一条从未端到端执行过的流水线不是流水线，是计划**。如果第一次端到端跑发生在有真模型的那天，
harness 的每个 bug 都会静默变成"能力结果"。

事实证明这个判断是对的：这次试运行抓出了 **4 个缺陷**，其中 2 个会让整个矩阵静默归零。

## 试运行抓到的缺陷

| # | 缺陷 | 后果 | 归属 |
| --- | --- | --- | --- |
| 1 | `CANDIDATE_SCHEMA` 是死常量，从未被读 | 别的 harness 的报告被判 ACCEPT | #250，已修 `7c19876` |
| 2 | 身份回显被硬 REJECT | 每条运行都 REJECT（假失败污染） | #250，已修 `721b31e` |
| 3 | 物体名叫 `target`/`goal`/`version` 被判"篡改不可变字段" | **24/24 静默 REJECT** | #250，已修 `16e7ca5` |
| 4 | `editable_fields` 写目录形式授权不了任何文件 | **24/24 静默 REJECT** | #250，已修 `16e7ca5` |

第 3、4 条是这次试运行的直接产出：它们不会让任何一条现有测试变红（7 例语料用的是
`block_a`、且 `editable_fields` 用的是文件形式），只有把 24 槽真跑一遍才会暴露。

## 试运行结果

`
python3 experiments/repair_eval_v02/dry_run_matrix.py
`

| 项 | 值 |
| --- | --- |
| 槽位 | 24 / 24（2 族 × 4 条件 × 3 次） |
| 状态 | 24 `DRY_RUN_COMPLETE` |
| 裁决 | 24 `ACCEPT`，`codes` 全空 |
| 可见性一致性 | 24/24 的 `gate/` 为 `sealed_material` |
| `policy_fingerprint` | `a48651c0…` |

### 这个结果不能说明什么（重要）

**4 个条件全部 6/6 ACCEPT，是因为 agent 是固定脚本**——它在每个条件下都执行同一个已知修复。
所以这份记录**不能**用来比较条件之间谁更好，也**不能**说"反馈没用"。要回答那个问题必须有真模型，
因为只有模型的行为才会随信息供给变化。

它证明的是**机制**：条件路由确实给了不同信息（见下表），判定确实按契约执行，门确实把评估器封印了。

| 条件 | 反馈通道实际返回 |
| --- | --- |
| A_STATIC | `policy_denied`（拿不到，符合协议） |
| B_REAL_FEEDBACK | `missing_material`（本试运行没有真运行产物） |
| C_MISMATCHED_FEEDBACK | `present`（从固定 donor 取，符合协议） |
| D_GUIDED | `missing_material` + 指导文本 |

B 和 D 返回 `missing_material` 不是缺陷：试运行没有"上一条真实执行"可供回放。真跑时这里应当是
本 run 的执行日志。

## 复现

`
git checkout codex/evobot-paper-v02-control-runs
python3 experiments/repair_eval_v02/dry_run_matrix.py | head -40
`

输出里每行都带 `"qualification": "DRY_RUN"`，汇总里带
`"qualification": "DRY_RUN_SCRIPTED_AGENT_NOT_A_MODEL_RESULT"`。

## 真跑还缺什么

| 项 | 状态 |
| --- | --- |
| 模型凭据（gate 脚本或 env 文件） | **缺** |
| 执行源码 40 位 SHA 冻结 | 缺（分支仍是候选） |
| 镜像 digest、模型 id、提示 sha256 | 缺 |
| `seed` 与 C 的 donor 绑定 | 缺（协议标 TBD） |
| 运行窗口与串行约定 | 缺 |

在这些补齐之前，本目录的记录保持 `DRY_RUN`，不计入 `ADMISSION.md` 的任何一项。
