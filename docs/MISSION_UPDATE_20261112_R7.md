# MISSION UPDATE — goal round 5 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮：去做 P3 能力工作，结果发现 P3 的门根本没开

第 3、4 轮是测量纪律。本轮本该是 P3 能力工作，所以我**把改进事件链端到端跑了一遍**，
问它是真的改进东西，还是只是产生文件。

```bash
python3 evolution/proposals/run_loop.py
```

它跑起来了，产生了提案。**它没有门。**

## §19.2 缺陷 1：回归门被显式关掉

`evolution/proposals/run_loop.py:68`：

```python
ok, reason = regress.gate(proposal, run_regressions=False)   # 而 gate 默认是 True
```

`regress.gate` 自己的 docstring 说它是「让 Baseline C 区别于『让 agent 改代码』的那道守卫」。
**调用方要求它不要做判断。**

关掉回归后，门只剩四项结构检查。**一个会弄坏仓库里每一个 verifier 的提案也会被 ACCEPTED 并写盘。**

## §19.3 缺陷 2：关掉的原因是真实的

我把它打开并按正确方式跑了一遍：**109 个 verifier 里 105 个通过，4 个因与任何提案无关的原因失败。**

所以「全绿门」会永远拒绝一切。有人把它关掉，而不是改成**差分**门——
**这就是为什么它从来没有拦下过任何东西。**

## §19.4 缺陷 3：冻结验证器校验的是被取代的基线

**我先修正了自己的初稿。** 初稿说「冻结契约漂移 5 次、冻结规则被违反」——**太强，发表前查掉了。**

项目有**正式的重新钉定流程**（`evobot_freeze_change_20261111/`，commit `102d0df5`：
「formal pinned-file change, grading proven identical」）。基线有**三代**：

| 代 | 当前漂移 |
| --- | --- |
| `evobot_capability_freeze_20261111`（最老） | **4** |
| `evobot_freeze_change_20261111` | **3** |
| `benchmark/capability_baseline.json`（**在用**） | **1** |

所以冻结被**维护过**，不是被抛弃。真正的缺陷更窄，其中一条更锋利：

- **在用基线只有一处漂移**：`benchmark/evaluators/evaluate.py`（`c75eaf78…` → `441903f1…`），
  在 `4fd36cd6`（2026-11-12）改动后未更新基线
- **`evobot_capability_freeze_20261111/verify.py` 校验的是最老那一代**，已被正式取代两次，
  **却从未退役**，于是它在「本就该改变」的文件上永久失败——**它正是让门保持关闭的四条原因之一**

## §19.5 两处只在你真正运行门时才出现的发现

### (a) 门不是只读的

跑完 109 个 verifier 后，一个已提交的证据文件被修改了：

```
 M setup/acceptance/evobot_p2_feasibility_20261111/verify_result.json
```

**109 个 `verify.py` 里有 108 个会写自己的 `verify_result.json`。**

所以开启回归门，会**顺带重写它所检查的归档证据**。
一个会修改它所读取证据的门，无法证明该证据未被改动。
（我已 `git checkout` 还原；记录影响，不保留它。）

### (b) 验证器可以因为「世界变好了」而失败

同一份 diff 暴露了那个 verifier 在断言什么、以及为什么现在失败：

```
claim B2:「no displacement/push clause: 'push' appears nowhere in the evaluator's goal handling」
  记录时: true
  现在  : false  —— push 子句由 0dc1245b 加入
```

**它失败是因为后来的提交补上了它记录的缺口。** 不是回归，是**过期前提**：
一份写着「现在还无法评分」的预注册，在可以评分之后从未退役。

一般形式：

> **形如「X 目前不存在」的验证器，在 X 被加入的那一刻就永久为假，然后堵住所有包含它的门。
> 前提类验证器需要退役日期，不只是创建日期。**

4 条失败中，**2 条是过期记录而非真实缺陷**（`capability_freeze`、`p2_feasibility`）；
另外两条（`baseline_a_v0`、`t08_push_criterion`）本轮未调查 → **UNKNOWN**。

## §19.6 一次性副作用

跑循环时 `evolution/proposals/actuator_stall.json` 被**就地覆盖**（那是一个待审提案）。
已 `git checkout` 还原。**`run_loop.py` 会原地重写提案文件**——待审提案可被一次重新生成静默替换。

## §19.7 能力等级（不膨胀）

| 项 | 等级 |
| --- | --- |
| P3 改进链 | **未打通**——门关闭、证据会被自身运行修改 |
| P3 Baseline C | **未达成** |
| T08 | 未变，skill 级 **0/6** |
| P0 A′ vs B | 仍无法区分 |
| L4 Develop | **未跨过** |

## §19.8 待人工决定（累积）

1. `place_server.py` 释放判据（第 1 轮提出；第 4 轮证明其安全论证有误、判据空转）
2. 提案拆分 part 1 / part 2
3. 修正 anti-gaming 论证
4. 复用开口度上限 + lift 门
5. **更新在用基线中的 `evaluate.py`**（附「grading proven identical」证据，或记录哪些数字早于该改动）
6. **退役或重定向 `evobot_capability_freeze_20261111/verify.py`** 到在用基线
7. **`freeze_check.txt` 由验证器生成，不得手写**
8. **把跳过的门换成差分门**——相对记录基线不引入**新的**失败
9. **让验证器只读**（或写入临时路径），使门无法修改证据
10. **`run_loop.py` 停止覆盖提案文件**

## §19.9 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0**（本轮全为离线） |
| 孤儿进程 | 0 |
| 冻结文件改动 | **0** |
| 阈值 / spec / 判决改动 | **0** |
| 日志泄露：记录并还原的副作用 | 1（`p2_feasibility/verify_result.json`、`actuator_stall.json`） |
