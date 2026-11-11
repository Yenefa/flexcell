# MISSION UPDATE — goal round 7 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮：把 P3 的门打开

第 5 轮证明改进链**没有门**：`run_loop.py` 用 `run_regressions=False` 调用回归门，因为 109 个 verifier 里有 4 个
因与任何提案无关的原因永久失败——全绿门会永远拒绝一切。于是门被关掉，而不是改成差分。

**门被关掉就等于不存在。** 本轮把它建成差分门。

## §19.2 做了什么

| 文件 | 作用 | 是否被钉定 |
| --- | --- | --- |
| `evolution/validation/known_failures.json` | 四条既有失败，逐条分类并写明理由 | 新增 |
| `evolution/validation/gate_differential.py` | 门：结构检查 + **不引入新失败** + 副作用还原 | 新增 |
| `evolution/validation/test_gate_differential.py` | 七项测试 | 新增 |
| `evolution/proposals/run_loop.py` | **修改**：改调差分门 | 未被钉定 |

`evolution/validation/regress.py` 是**被钉定的，未改动**——新门只读地导入它并委托结构检查。

## §19.3 规则

```
基线内失败，仍然失败          -> ACCEPT（未变）
基线内失败，现在通过          -> ACCEPT，并报为改进
不在基线内的失败              -> REJECT  <-- 这就是门
known_failures.json 缺失      -> REJECT（基线缺失不得成为放行）
找不到任何 verifier           -> REJECT（绝不接受未测试）
```

## §19.4 端到端证据

```
$ python3 evolution/proposals/run_loop.py
measured failures across all archives: 101
  GATE  actuator_stall         n=50  ACCEPTED
         structure ok; 109 verifier(s) run; 4 known failure(s) unchanged; 0 new
         [restored 1 archive file(s) the verifier run rewrote]
  GATE  occupied_destination   n=5   ACCEPTED
         structure ok; 109 verifier(s) run; 4 known failure(s) unchanged; 0 new
         [restored 1 archive file(s) the verifier run rewrote]
```

改动前同一行是 `structure accepted (regressions skipped by caller)`。
**差别是每个提案 109 次独立验证，此前一次都没有。**

跑完后**没有任何 `verify_result.json` 处于修改状态**——还原在真实环境里成立，不只单测里成立。

## §19.5 我自己犯的两个错，都记录下来了

### (a) 错的是我的测试，不是门

我把某个 verifier 放进基线，却去跑**另一个** verifier，然后期待出现「cleared」提示。
基线内的失败只有在**真的被跑过**时才能被报为 cleared。**我改的是测试。**

### (b) 我第一版用 git 还原——而 git 在这个 worktree 的 WSL 里不能用

`wt-comp` 的 `.git` 指向一个 Windows 绝对路径：

```
fatal: not a git repository: .../wt-comp/C:/Users/fuker/.../code_worktrees/wt-comp
```

于是两个 helper 都抛异常，`_dirty_paths()` 返回空集合，**还原静默地什么都没做，而门报告成功。**
我是**因为跑完整轮后文件仍然是脏的**才发现的——
**与本文件里记录的每一种失败同形：组件报告了它并未达成的结果。**

改成字节快照（不使用 git），并收窄范围到每个 verifier 目录下一层
（原先递归扫 `setup/acceptance/` 让 6 个单测跑过 2 分钟而超时）。

验证：

```
verify_result.json sha before : d1ef15f46b50a2e3
verify_result.json sha after  : d1ef15f46b50a2e3
RESTORED EXACTLY             : True
```

## §19.6 基线是诚实的：两条仍是 UNKNOWN

| verifier | 分类 |
| --- | --- |
| `evobot_capability_freeze_20261111` | **STALE_RECORD** — 校验被取代两次的最老基线，从未退役 |
| `evobot_p2_feasibility_20261111` | **STALE_PREMISE** — 因后续提交**补上**了它说缺失的 push 子句而失败 |
| `evobot_baseline_a_v0_20261111` | **UNKNOWN** — 未调查 |
| `evobot_t08_push_criterion_20261111` | **UNKNOWN** — 未调查 |

**把失败放进基线，不等于宣称它是良性的**，只等于宣称它无法归因于某个提案。
说成前者，就是这个项目已经犯过六次的「用标签替代原因」。

## §19.7 顺便确定的事：T08 的卡点在运动学，不在判决

`move_to_pose` **接受带姿态的完整 `PoseStamped`**，所以腕部姿态在原理上可命令。
但 URDF 分析（第 2 轮）显示掌体沿 link5 x 约 82 mm，而手臂**可达的下限正好是块顶 0.035**。
要接触侧面中部（0.0175）需要换工具或改机器人描述——**需要批准，本轮未尝试。**

## §19.8 能力等级（不膨胀）

| 项 | 等级 |
| --- | --- |
| 差分门 | **Designed → Implemented → Unit Tested（7/7）**；**未** Simulation Tested，**未** Independently Verified |
| 它是测试基础设施，**不是机器人能力** | — |
| T08 skill 级 | **0/6，未变** |
| P3 事件链 | **未完成**：门恢复了，但**没有任何改动被应用并重测**，七字段经验记录**未交付** |
| L4 Develop | **未跨过** |

## §19.9 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0** |
| 孤儿进程 | 0 |
| 钉定文件改动 | **0**（`regress.py` 只读导入） |
| 阈值 / spec / 判决改动 | **0** |
| 删除失败证据 | **0** |
| 还原的副作用 | 每轮门调用 1 个 `verify_result.json`（已字节级还原） |
