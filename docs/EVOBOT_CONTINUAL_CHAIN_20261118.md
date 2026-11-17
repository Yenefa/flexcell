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
| ① 抽出一个机制 | `evolution/experience/schema.py` | v2 条目：来源、原始证据、适用任务、适用条件、已知失效条件、置信状态、验证记录（master goal §11.2 的七字段），外加 **consumer / action_kind / effect_spec / invalid_probes / version** |
| ② 转成经验条目 | `schema.make_entry` + **`postmortem.py`** | 缺 effect_spec 的条目在写入时即被拒绝——**不能被执行的"效果"只是主张**；条目现在**从归档运行日志自动生成**，不是人手写 |
| ③ 形成可用产物 | `consumers.py` | 消费模块**主动声明**自己能执行哪些 `action_kind`；条目按能力路由，而不是按关键词猜地址 |
| ④ 本地验证后再启用 | `effect.py` + `regression.py` + `misuse.py` + `curate.py` + `retrieve.py` | 效果**被执行**再判定；**回归门 KEEP 才允许启用**；**误用检查 BLOCKED 才允许启用**；重复/冲突拒绝；检索要求独立 ACCEPT；启用采用**追加式**版本链 |
| ⑤ 记录后续使用效果 | `ledger.py` + `lifecycle.py` | RETRIEVED / APPLIED / OUTCOME 三类事件分开记；`effect_of()` 只从事件推导状态；**有害则停用（追加式 RETIRE）** |
| ⑥ 沉淀为可执行技能 | `skill_asset.py` | ACTIVE 且已审核的条目**编译成可调用资产**（模块+函数+绑定参数+失效护栏），可被后续任务直接调用 |

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

## 4.5 条目从哪来：自动生成，不自审（master goal 第 1、2 步）

上一轮所有条目都是脚本里手写的。**只有人手输入经验的管道不是持续演进，是带校验的表单。**

`postmortem.py` 扫归档运行产物，按**可观测签名**聚类，满足门槛才产出 CANDIDATE 条目：

| 规则 | 理由 |
| --- | --- |
| 至少 **2 次**出现 | 本仓库曾把单次运行的观察当教训发表，后来发现是错误归因 |
| evidence 只取**解析出来的字段** | 散文是"关于测量的主张"，不是测量 |
| 消费者必须**已声明且入口存在** | 否则报 UNROUTED——"这个栈没地方放这条知识"是真实发现，不该用猜测掩盖 |
| effect_spec 必须**可执行** | 否则报 NOT_READY，不产出一条"效果只能被断言"的条目 |
| 失效条件与探针**必须一一对应** | 否则报 NOT_READY，避免下游必然 UNPROBED |
| 永不写 ACCEPT | 生成者自审会让审阅门、回归门、误用门**同时**变成摆设 |

**在真实归档上的结果（51 次失败）**：

| 签名 | 次数 | 结果 |
| --- | --- | --- |
| `occupied_destination` | 5 | **生成条目**，路由到 `spread_policy` |
| `unconfirmed_native` | **46** | **UNROUTED**：本栈没有能执行"resume from measured state"的可调用函数 |

46/51 的失败**在本栈里无处安放**——这是关于这个机器人栈的发现，不是脚本的缺口。
把它硬塞进一个 `respread_apply` 的 effect_spec 里，测的就是另一个函数，
那正是"经验送给没能力执行它的模块"的同一类错误。

## 5. 检索门（四道，每道都对应一次真实事故）

1. **哈希链完好** —— 链断即拒绝整库（不"尽量学一点"）
2. **独立 ACCEPT** —— 只有 provenance 不算数：曾有两条通过 provenance 的记录在审核后被判为假，
   且它们在审核**之前**就能被检索到，并影响了计划
3. **能力匹配** —— 消费模块必须声明该 action_kind
4. **状态 ACTIVE** —— CANDIDATE / RETIRED / REJECTED 一律不进计划

## 5.5 回归门：决定"保留还是回退"（DGM 式）

启用不是"审核通过就上线"。`regression.check()` 按条目所属消费模块跑**固定的一组**验收验证器，
与 `known_failures.json` 比对：

| 结果 | 含义 | 后果 |
| --- | --- | --- |
| **KEEP** | 没有新增失败 | 允许启用 |
| **REVERT** | 出现**新增**失败 | 拒绝启用，候选留在库里 |
| **UNKNOWN** | 门跑不起来（无验证器 / 基线不可读） | **同样拒绝**——"检查不了"不等于"没问题" |

这条"UNKNOWN 不是通过"的规则来自本仓库的真实教训：`gate_differential.py` 记录过一次，
"缺少基线"曾被当成放行。启用记录里会写下 `regression.verdict` 与实际跑过的验证器名，
所以"过了回归"是可复算的陈述，不是形容词。

## 5.55 误用检查：不适用场景下会不会被打出去（master goal 第 4 步）

回归门问的是"旧任务还过不过"，它**问不了**"这条经验会不会在它自己声明做不到的场景里被打出去"。
所以 `misuse.py` 把 `known_invalid_when` 里的每一条**变成一个真实输入**，真的调用消费模块：

| 结果 | 含义 | 是否放行 |
| --- | --- | --- |
| **REFUSED** | 消费模块抛错，拒绝发出不可执行的结果 | 放行 |
| **INERT** | 消费模块原样返回，什么也没改 | 放行 |
| **APPLIED** | 在被声明不适用的场景里真的改了结果 | **MISUSABLE，拒绝启用** |
| **UNPROBED** | 声明了失效条件但没有任何可执行探针 | **拒绝启用** |

**UNPROBED 不放行**是本轮的关键判断：一条"写了免责声明但没人验过"的经验，
和一条"没人验过的门"是同一个东西。schema 还拒绝**部分覆盖**——声明三条只探测一条，
会让读者以为三条都查过了。

实测三条声明全部成立：单阶段落点 → INERT（原样返回）；三个物体进 60 mm 箱 → REFUSED；
窄箱（30 mm）→ REFUSED。执行侧三条同样成立，其中"走廊被占"→ REFUSED（两轴都不满足间隙契约）。

## 5.56 生命周期：按实际结果停用（master goal 第 5 步）

`ledger.py` 能算出 `used_harmful`，但在上一轮它**算完就丢掉了**——一条把运行变差的经验
会继续 ACTIVE、继续被检索。那不是闭环，是报告。

`lifecycle.py` 把它接上：

| 判定 | 条件 | 动作 |
| --- | --- | --- |
| **KEEP** | 无有害结果（含从未使用） | 不动 |
| **RETIRE** | 被应用过，且至少一次结果是 WORSE | 追加一个 RETIRED 后继版本 + 记 RETIRED 事件 |

**从未使用不等于有害**，所以不会因为"没人用过"就退休——沉默不是伤害的证据。

**一个必须讲清的坑**：`entry_id` 是对 body 取的摘要，而 body 含 `version.status`，
所以每次状态转换都会得到**新 id**；而 store 是追加式的，退役后**旧记录仍然写着 ACTIVE**。
第一版检索只按单条记录的 status 判断，于是退役之后**照样检索得到**——退役动作产生了零可观察变化。
修法是让检索与生命周期都按**版本线**判断：任何被后续记录声明为 parent 的 id 视为已被取代。
本轮为此加了 `superseded_ids()` 与 `latest()`，并有一条测试专门守"退役后检索必须拿不到"。

## 5.6 Voyager 式技能资产

一条经验只有在**能被下一次任务直接调用**时才算技能，否则它只是一条需要人读的笔记。
`skill_asset.compile_asset()` 把 ACTIVE 且 ACCEPT 的条目编译成资产：

```json
{"asset_id": "skill.executor_recovery.ee7177a04560",
 "callable": {"module": "runtime.recovery.recover", "function": "apply_respread",
              "kwargs": {"spread_step": 0.09, "cluster_m": 0.12}},
 "guard": ["a single stage lands in the bin", "..."],
 "source_entry": "ee7177a04560...", "code_generated": false}
```

三条硬约束：
- **参数必须有绑定**：effect_spec 里出现、但该消费模块没有对应形参的键，**拒绝编译**而不是静默丢弃
  （静默丢弃会让资产做的事与条目说的不是一回事）；
- **必须有护栏**：`known_invalid_when` 为空即拒绝——没有护栏的技能可以在已知会失败的场景被调用；
- **不生成新代码**：`code_generated: false` 写进资产。把自然语言直接变成机器人代码，
  本仓库没有证据支持，所以只把**已验证的参数改动**绑定到**已测试的函数**上。

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
| 经验条目的自动生成 | **已做**：`postmortem.py` 从 51 次归档失败生成 1 条、拒绝 1 类（46 次）并给出理由；但签名→消费模块的映射表仍由人维护 |
| GEPA 式候选搜索 | **未做**：本轮只做单候选，多候选与成本权衡留待后续 |
| 技能资产的自主编排（组合已有资产完成新任务） | **未做**：本轮只到"资产可被调用"，没有组合 |
| 回归门覆盖全部 109 个验证器 | **未做**：按消费模块固定子集（2 个），全量跑约数分钟且大多与本条目无关 |
| RETIRE 的**真实触发** | **未做**：本轮没有任何运行把结果变差，所以退役只在**副本 + 合成有害事件**上演示；真实 store 未被触碰 |
| 误用探针的覆盖面 | **有限**：5 个探针覆盖落点/重排两类消费者，其它消费模块（harness、development）尚无探针 |

## 8. 复算方式

```bash
python3 setup/acceptance/evobot_continual_chain_20261118/verify.py
python3 evolution/experience/demo_continual.py
python3 -m pytest evolution/experience/test_continual_chain.py -q
```

verifier 会**重新执行**整条链并断言 **34 项检查**，不读取 SUMMARY 里的自述。其中关键几项：

- 规划侧不生效（NO_CHANGE）、执行侧生效（CHANGED）；
- 启用前后检索分别为 0 与 1；
- 启用记录里带 `regression.verdict == KEEP` 且**真的跑过验证器**；
- 启用记录里带 `misuse_check.verdict == BLOCKED`，且**每条声明的失效条件都被探测过**；
- ACTIVE 条目编译出的资产**绑定到一个真实存在的可调用函数**，且 `code_generated == false`；
- **被拒绝的投递（E1）不产出任何资产**——资产是可调用的，只有过审且过回归的条目才配变成技能；
- 生命周期复盘给出 KEEP/RETIRE 判定，**退避转换真的追加了 RETIRED 版本**、父指针正确、链仍完好；
- 退役演示跑在**副本**上，真实 store 仍只有一个 ACTIVE 条目；
- **至少一条条目来自归档自动生成**，生成器拒绝了一个 UNROUTED 签名，且**没有任何生成记录在无具名审阅者时被 ACCEPT**。
