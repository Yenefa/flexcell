# MISSION UPDATE — goal round 12 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮：把 P3 的「七字段经验记录 + 独立审核」真正做了，结果是 0/4 合格

经验记录一直存在（4 条，hash 链完好），**但仓库里没有任何「第二方审过」的痕迹**。
本轮补上：先我自己审计，再请 `gate-auditor` 独立复核——我在委托里明确要求「宁可告诉我四条里三条是弱的」。

**结果：0 ACCEPT / 1 ACCEPT-WITH-CORRECTION / 3 REJECT。**

## §19.2 系统性成因（审核找到的，比我找的更好）

> **归档里放的是修复后的 run，而证据描述的是修复前的失败。**
> 缺陷在目录归档之前就被修好了，所以被引用的来源**在构造上不可能**包含那条证据。
> 一个照着 `source_run` 去做「打开来核对」的读者，在 4 次里有 3 次会看到一个**通过的 run**。

我自己的审计止步于「证据只存在于散文里」；审核给出了**为什么**。

我**自己复核了它两条最锋利的断言**，没有直接采信：

| 断言 | 我的核对 |
| --- | --- |
| R1 引用的 run **通过了**，与记录里的 `outcome: failed` 矛盾 | **确认**：`evobot_t01_baseline_a_20261111/task.out` = `{ok:true, outcome:0, error_code:0}` |
| R4 的 `task_id` 在其引用来源里根本不存在 | **确认**：`T03-heldout-seed9000` 出现 **0 次** |

## §19.3 审核还查出两件我没查的事

**(a) `validated: true` 不等于「被审核过」。**
`store.make_record` 在 `store.py:56` 设为 `False`，`seed_from_evidence.py:31` 在 append 前**覆写为 True**。
它记录的是「播种器跑过了」，却用了一个所有读者都会理解为「第二方查过了」的字段名。

**(b) 作用域守卫没有守住它声称的东西。**
8/8 的 lesson/evidence 都通过 `_check_scope`，**而 3/4 的 lesson 根本不是 planner 级**。
它是防「夹带答案」的关键词黑名单，**对一个同义词毫无抵抗力**（R4 写「landing spots」而不是「placement」）。
**可被一个同义词绕过的黑名单不是边界。**

## §19.4 我自己的审计结论

| 项 | 值 |
| --- | --- |
| 能改变计划的 lesson | **1 / 4**（2 条 HARNESS，1 条 DOWNSTREAM_CODE） |
| 那一条 actionable 对应的失败 | `error_code 64`——**在任何机器可读的归档文件里都不存在**，只出现在 3 个 README |
| 确切引用证据能在机器可读文件里找到的记录 | **0 / 4** |

## §19.5 一处分歧，我记录而不是挑好看的那个

审核称 R3 的证据是「真实的（唯一一条证据在真实 run 日志里）」。
**按引用字符串核对，这没有被确认**：`Failed to find a free participant index for domain **213**`
只出现在该批次的 `README.md:19`。

而 `runs/s1004-a1/stack.log` 里是**同一类失败、不同数字**：`domain **233** participant index 0`。

所以它更宽的说法有依据（DDS 名额耗尽确实发生过并被记录），**而它具体的断言不成立于记录所写的内容**。
两种读法都记下来，我不挑更好看的那个。

## §19.6 P4 现在可以用「机制」而不是「没测」来回答

| 层 | 发现 |
| --- | --- |
| 检索 | 4 条里 1 条能作用于计划 |
| 那一条 | 针对一个在任何机器可读归档里都不存在的错误码 |
| 证据 | 4 条里 0 条能从自己引用的来源重新推导 |
| 因此 | **一个复用该经验库的 D 臂，只有一条关于「从未观测到的失败」的 lesson，且证据不可验证** |

> **EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED —— 机制是：经验通道里没有任何一条 lesson 能作用于本项目跑过的
> 任何任务，所以经验复用臂没有东西可复用。**

**但我没有宣布 P4 完成。** D 的定义仍未形式化（`§7.5` 说它不能保持未定义，同时又说那只是待 North Star
确认的建议，而 North Star §8–§14 是 `BLOCKED_MISSION_TEXT_MISSING`）。本轮确立的是**任何未来 D 都会继承的
前置条件失败**。

## §19.7 待人工决定（新增）

审核给出的排序修复，**全部未实施**（它们改经验流水线，其中两条改记录 schema）：

1. **让播种器机械地验证来源**——断言证据值确实出现在 `source_run` 下的某个文件里。约 10 行，
   仅此一项就会拒掉 3/4。**这是「声明」和「检查」的区别。**
2. `source_run` 指向 **run**（`runs/s1000-a1`），不是批次目录。
3. **修缺陷时归档那次失败的 run**——三处错引都来自「修好 bug 只归档成功」。
4. 用审核者写入的显式字段（`reviewed_by` / `review_verdict` / `review_ref`）取代 `validated: true`。
5. 把 `audit_actionability` 接进**写路径**。

## §19.8 证据等级

| 声明 | 等级 |
| --- | --- |
| P3 七字段记录「格式满足、链完好、**0/4 按原样可接受**」 | **独立审核 + 我复核** |
| 经验通道**可被填充**、完整性机制**能运行** | **已证明** |
| 经验通道**有效** | **未证明** |
| P4 | **未完成**，但已给出 `EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED` 的机制 |
| T08 skill 级 | **0/6，未变** |
| L4 Develop | **未跨过** |

## §19.9 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0** |
| 孤儿进程 | **0** |
| `evolution/` 改动 | **0**（git status 为空） |
| 钉定文件改动 | **0** |
| 记录被改写 / 被删除 | **0** |
