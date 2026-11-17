# 持续演进主线：经验条目 → 消费模块 → 实际行为 → 验证结果

**状态：已实现并通过离线链路验证；未做新的机器人运行**
**入口：** `evolution/experience/` · **证据：** `setup/acceptance/evobot_continual_chain_20261118/`
**日期：** 2026-11-18 · **基线：** `39016694`（`evo/continual-experience`）

---

## 1. 这一轮要解决的具体问题

前几轮的结论是"经验没有效果"：B/C 两组实验产出**逐字节相同的计划**。审计找到原因不在经验本身，
而在**投递地址**——经验讲的是落点坐标，而规划器只输出"物体→区域"，永远没有字段去放坐标。

所以本轮不新增经验条目，而是把下面这条链接通，并让它可被机器复算：

```
实测失败 → 经验条目 → 消费模块 → 实际行为变化 → 验证结果 → 使用记录
```

## 2. 五步"吸取与炼化"，逐步落到代码

| 步骤 | 本轮落点 | 机制 |
| --- | --- | --- |
| ① 抽出一个机制 | `evolution/experience/schema.py` | v2 条目：来源、原始证据、适用任务、适用条件、已知失效条件、置信状态、验证记录（master goal §11.2 的七字段），外加 **consumer / action_kind / effect_spec / version** |
| ② 转成经验条目 | `schema.make_entry` | 缺 effect_spec 的条目在写入时即被拒绝——**不能被执行的"效果"只是主张** |
| ③ 形成可用产物 | `consumers.py` | 消费模块**主动声明**自己能执行哪些 `action_kind`；条目按能力路由，而不是按关键词猜地址 |
| ④ 本地验证后再启用 | `effect.py` + `curate.py` + `retrieve.py` | 效果**被执行**再判定；重复/冲突拒绝；检索要求独立 ACCEPT；启用采用**追加式**版本链 |
| ⑤ 记录后续使用效果 | `ledger.py` | RETRIEVED / APPLIED / OUTCOME 三类事件分开记；`effect_of()` 只从事件推导状态 |

## 3. 消费模块能力表（写死在代码里，可被测试检查）

| consumer | 能执行的 action_kind | 入口 | 投递方式 | 能否离线测量 |
| --- | --- | --- | --- | --- |
| `planner` | move_order, object_set | `runtime/planner/agent_planner.py::describe` | prompt | **否**（需要模型调用，报 UNMEASURED） |
| `spread_policy` | landing_spacing | `runtime/planner/spread_destinations.py::spread` | 参数 | 是 |
| `executor_recovery` | recovery_action | `runtime/recovery/recover.py::apply_respread` | 参数 | 是 |
| `harness` | harness_config | `config/cyclonedds.xml` | 配置 | 否 |
| `development` | development | `development_skills/registry.json` | 文档 | 否（开发实践不是机器人经验） |

**一个条目被路由到不能执行它的模块，会被直接拒绝**，而不是被静默改投。这正是旧
`route_lessons.py` 用关键词路由时出过一次的错（domain-id 教训里含 "distinct"，被投给了落点代码）。

## 4. 本轮实测到的结果（这是重点）

同一条落点经验，同一份归档计划（`HO-90899d657e68`），投给两个消费模块：

| 投递地址 | 结果 | 机制 |
| --- | --- | --- |
| 规划侧 `spread()` | **NO_CHANGE** | 按**完全相等的落点**分组；计划构建器早已把两个落点错开 56 mm，没有可分的组 |
| 执行侧 `apply_respread()` | **CHANGED** | 按**距离聚类**，找到这一对，把间距从 56 mm 拉到 90 mm |

也就是说：**"经验没有效果"对某个地址成立，对另一个地址不成立**——同一仓库、同一条经验、同一份输入。

执行侧在原实现里还有一个真实缺陷，本轮一并修掉并写明边界：
`apply_respread` 只会沿 +x 展开，在这份计划上把第二个落点推到距 box_b 46 mm（< 50 mm 契约），
于是重试第三次被拒为"declared destination occupied"。修改为**按余量选轴**，并且两轴都不满足契约时**拒绝**而不是发出一个必然被拒的计划；
不传 avoid 时行为与旧实现**逐字节相同**，11/11 `benchmark/tests/test_recovery_driver.py` 仍通过。

## 5. 检索门（四道，每道都对应一次真实事故）

1. **哈希链完好** —— 链断即拒绝整库（不"尽量学一点"）
2. **独立 ACCEPT** —— 只有 provenance 不算数：曾有两条通过 provenance 的记录在审核后被判为假，
   且它们在审核**之前**就能被检索到，并影响了计划
3. **能力匹配** —— 消费模块必须声明该 action_kind
4. **状态 ACTIVE** —— CANDIDATE / RETIRED / REJECTED 一律不进计划

## 6. 版本与回滚（DGM 式）

- 每个版本有 `parent_entry_id`；启用 = **追加**一个 reviewed successor，候选体保留在库中
- 重写会让哈希链把整库判为篡改，所以"激活"从不修改历史
- 失败分支保留而非删除：被拒绝的投递（E1）与成功的投递（E2）在同一份证据里并存
- `curate.curate()` 区分"重复"与"版本链"，避免把 reviewed successor 记成重复而重复计数

## 7. 明确的未完成项（不得当作已有能力）

| 项 | 状态 |
| --- | --- |
| 外部（非同一运行内）独立审核 | **未做**：本轮的 review 由同一运行中的独立步骤写出 |
| 新机器人运行验证 | **未做**：所有结果来自归档输入 |
| 规划器（prompt 层）效果测量 | **不可离线测量**，报 UNMEASURED |
| 跨任务族迁移 | **未验证**：当前 ACTIVE 条目只覆盖 T13 任务族，n=1 |
| 经验条目的自动生成（从运行日志到条目） | **未做**：条目仍由脚本构造 |
| GEPA 式候选搜索 | **未做**：本轮只做单候选，多候选与成本权衡留待后续 |

## 8. 复算方式

```bash
python3 setup/acceptance/evobot_continual_chain_20261118/verify.py
python3 evolution/experience/demo_continual.py
python3 -m pytest evolution/experience/test_continual_chain.py -q
```

verifier 会**重新执行**整条链并断言 14 项检查（其中包含"规划侧不生效、执行侧生效"与
"启用前后检索分别为 0 与 1"），不读取 SUMMARY 里的自述。
