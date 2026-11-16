# TASKS — 任务族定义与保留场景（v0.1 草案）

> **状态：DRAFT v0.1。未冻结。未执行。**
> 本文档定义「用户目标不变、执行者可改什么、什么算保留场景」。
> 所有数值型容差引用 **base `2ca40ebe` 上的冻结评估器**，本文档不改它们。

## 1. 总则：什么永远不变

以下四类东西对执行者**只读**，改一项即触发 #250 契约负例，该记录判 `FAIL`：

| 类别 | 具体内容 | 冻结依据 |
| --- | --- | --- |
| 用户目标 | 任务的自然语言目标（"把 A 放到 zone_1，B 放到 zone_2"）与 `expected_goal` 语义 | 任务族定义（本文档） |
| 物体集合 | 物体名称、尺寸、颜色、初始位姿；区（zone）名称与位姿 | 冻结的 task spec |
| 容差 | 评估器内的容差常量与 zone 半径 | `benchmark/evaluators/evaluate.py`（sha256 见 §6） |
| 判定链 | G1 目标门 / G2 回归门 / G3 契约门 / G4 独立验收 | [PROTOCOL.md](PROTOCOL.md) §7 |

**执行者只能改「允许修改字段」(§2.3 / §3.3) 里列出的键或代码位置。**
允许字段清单本身在准入阶段冻结，运行中不得扩充。

## 2. 任务族 F1 — 对象注册缺失

### 2.1 缺陷

工作区配置的感知注册表只登记了物体 A，物体 B 未被注册，
因此双对象任务里 B 不会被感知、也不会被校验，任务在 `OBSERVE` 或 `PICK_B` 阶段失败；
只用 A 的保留场景仍应 PASS（所以回归门可用）。

| 项 | 值 | 状态 |
| --- | --- | --- |
| 缺陷实例 ID | `DEF-F1-REG` | DRAFT-FIXED |
| 注入位置 | 工作区配置中感知服务的对象注册参数（`tracked_objects` 一类键） | DRAFT-FIXED |
| 注入实现 | `experiments/repair_eval_v02/defects/DEF-F1-REG/override.yaml`（sha256 `6c4da05fe04e0ee8…`） | DRAFT-FIXED |
| 机制 | 注册表缺失 → 感知层不发布 B → 任务层取不到 B | DRAFT-FIXED |
| 机制（实测修正） | 原文写「注册表缺失」。2026-11-16 实测：`tracked_objects: []` 经 params 文件与 `--ros-args -p` 两种写法都触发 `ParameterUninitializedException`，节点启动即死——那是**另一种机制**。落成的注入改为注册一个世界里不存在的名字（`ghost_object`）：节点存活、感知层观察不到任何演示物体，任务层同样取不到 B。差异对修复者可见，登记在此而非默认化 | DRAFT-FIXED |

### 2.2 不可变目标

| 项 | 值 |
| --- | --- |
| 用户目标（自然语言） | 「把红色方块放进 zone_1，把蓝色方块放进 zone_2」 |
| 目标场景 | 双对象放置：`target_box_a → zone_1`，`target_box_b → zone_2` |
| 物体集合 | `target_box_a`、`target_box_b`（尺寸 / 颜色 / 初始位姿由该 seed 的冻结 spec 决定，执行者不可改） |
| 区集合 | `zone_1`、`zone_2`（位姿 + 半径由 spec 决定） |
| 容差 | 见 §1 与 §6；水平 0.02 m、静止高度 0.02 m、zone 半径取 spec 中的 `radius` |
| 不应移动 | `unmoved` 列表由 spec 决定，执行者不可改 |

### 2.3 允许修改字段（DRAFT-FIXED）

| 允许 | 说明 |
| --- | --- |
| 感知对象注册表的条目 | 补回 B 的注册项；修正键名/尺寸键 |
| 与该注册相关的合法配置键 | 例如对象尺寸参数 —— 仅当它能解释「B 未被感知」 |

**明确不允许**：改 zone 位姿/半径、改 `expected_goal`、改评估器、改容差常量、
删除或跳过任何保留场景、改 `protected` 文件清单。

### 2.4 预期失败与回归场景

| 项 | 值 |
| --- | --- |
| 预期失败阶段 | `OBSERVE`（B 缺失）或 `PICK_B`（`target_not_available` 类错误） |
| 回归场景（必须仍 PASS） | `normal`（只用 A 的单对象场景） |
| 修复成立的最小充分条件 | 双对象任务 PASS **且** `normal` 仍 PASS **且** 契约门通过 |

## 3. 任务族 F2 — 固定用户目标下的坐标变换 / 目标映射缺陷

### 3.1 缺陷

目标区的**映射源取错**：放置目标用「物体 A 所属的区」去索引区表，而不是用决策里
真正要放置的物体，于是 B 被指派到 A 的区（落错区），并且在若干实例上落到几何不可达的区
（历史观测：`zone_2 at (0.45, 0.05)` 超出可达范围）。保留场景（只用 A / 单对象）不受影响。

| 项 | 值 | 状态 |
| --- | --- | --- |
| 缺陷实例 ID | `DEF-F2-MAP` | DRAFT-FIXED |
| 注入位置 | 规划/放置技能中「物体 → 目标区」的映射来源（源码） | DRAFT-FIXED |
| 注入实现 | `experiments/repair_eval_v02/defects/DEF-F2-MAP/inject.patch`（由 #252 落成；补丁 sha256 `db1c48d3b94c330b…`；受影响文件见 manifest） | DRAFT-FIXED |
| 机制 | 映射源取错 → 目标区错误 / 不可达 → `PLACE_B` 失败或落错区 | DRAFT-FIXED |
| 备选但**不使用** | 配置坐标错（如把某 zone 的 x 写成不可达值）属**另一种机制**，不在 24 槽矩阵内；若要使用必须新预注册 | DRAFT-FIXED |

> **注意**：F2 的修复面是**源码**，F1 的修复面是**配置**。这两族在「修复成本」上不可直接比较，
> 因此 [ANALYSIS.md](ANALYSIS.md) 的主对比只做**族内**的 B vs A，不做跨族比较。

### 3.2 不可变目标

| 项 | 值 |
| --- | --- |
| 用户目标（自然语言） | 与 F1 同构：「把红色方块放进 zone_1，把蓝色方块放进 zone_2」 |
| 目标场景 | 双对象放置（同上），但缺陷机制不同 |
| 物体集合 / 区集合 | 由该 seed 的冻结 spec 决定，执行者不可改 |
| 容差 | 同 §2.2 |
| 附加约束 | 「固定用户目标」意味着执行者**不能**通过改指令、改目标或改容忍度来「达成」 |

### 3.3 允许修改字段（DRAFT-FIXED）

| 允许 | 说明 |
| --- | --- |
| 映射来源的取值位置 | 把目标区索引改回「按决策目标物体取」 |
| 同一函数内的坐标变换实现 | 仅当它属于该映射链路，且不改变对外接口 |

**明确不允许**：改 `expected_goal`、改 zone 定义、放宽任何容差、改评估器或 gate、
删除测试、改 `protected` 清单、改任务自然语言目标。

### 3.4 预期失败与回归场景

| 项 | 值 |
| --- | --- |
| 预期失败阶段 | `PLACE_B`（落错区）或 `MOVE`（目标不可达） |
| 回归场景（必须仍 PASS） | `normal`（单对象 A）+ `regrasp`（重抓取场景） |
| 修复成立的最小充分条件 | 双对象 PASS **且** `normal` / `regrasp` 均 PASS **且** 契约门通过 |

## 4. 保留场景清单与保留规则（对接 #253）

### 4.1 清单

| 场景 ID | 用途 | 适用族 | 判定阈值 | 状态 |
| --- | --- | --- | --- | --- |
| `normal` | 单对象 A 的基础放置 | F1、F2 | 冻结评估器 G1 | DRAFT-FIXED（清单） / `TBD`（具体 spec 与 seed，由 #253 固定） |
| `regrasp` | 重抓取路径 | F2 | 冻结评估器 G1 | DRAFT-FIXED（清单） / `TBD`（同上） |
| `dual_object` | 目标场景本体（不是保留场景，但必须每次一致） | F1、F2 | 冻结评估器 G1 | DRAFT-FIXED（清单） / `TBD`（同上） |
| 第三场景（可选） | 若 #253 认定需要第三保留场景 | 待定 | 待定 | `TBD`（由 #253 决定，决定后本表升版本） |

### 4.2 保留规则（DRAFT-FIXED）

1. **保留场景一旦固定，运行中不得增删**；增删即升版本（[PROTOCOL.md](PROTOCOL.md) §8.3）。
2. 保留场景的 **spec、seed、评估器、容差** 全部固定；不得为了「让它通过」而调整。
3. 一条记录只要**任一保留场景** FAIL → 该记录 `FAIL`（G2 失败），即使目标场景 PASS。
4. 保留场景的失败也要进表（不要只报目标场景）。
5. 若保留场景在**修前**就是 FAIL（缺陷把回归也打坏了），则该保留场景对本族**不成立**，
   必须由 #253 换场景并升版本，**不能**把「回归本来就坏」当成「修复没破坏回归」。

## 5. 与 #250 契约（`benchmark/repair_eval/contracts`）的计划接口

> **这是计划，不是已实现。** base `2ca40ebe` 上 `benchmark/repair_eval/` 目录**不存在**。

本包**需要** #250 提供下列能力（签名是计划草案，最终以 #250 交付为准）：

```python
# 计划接口 — 未实现，仅声明本协议的依赖面
from benchmark.repair_eval import contracts

# 1) 加载冻结的任务契约（不可变目标 / 物体集合 / 容差 / 允许修改字段）
c = contracts.load_contract(contract_path: str) -> TaskContract
#    TaskContract 计划字段：
#      contract_version: str          # 版本化契约，如 "repair-contract/0.1.0"
#      task_id: str
#      family: str                    # "F1" | "F2"
#      immutable_goal: dict           # 不可变用户目标（含 expected_goal 语义）
#      object_set: list[dict]         # 不可变物体集合（名称/尺寸/颜色/初始位姿）
#      zone_set: list[dict]           # 不可变区集合（位姿/半径）
#      tolerances: dict               # 容差来源与取值（引用冻结评估器常量）
#      allowed_edits: list[str]       # 允许修改字段/路径
#      protected_paths: list[str]     # 保护文件清单（hash 冻结）
#      regression_scenarios: list[str]# 保留场景 ID 清单

# 2) 校验一次候选修复，返回结构化判定与拒绝理由码
v = contracts.check(candidate_dir: str, contract: TaskContract,
                    evaluation: dict, evidence: dict) -> ContractVerdict
#    ContractVerdict 计划字段：
#      ok: bool
#      reason_codes: list[str]        # 见下表
#      false_accept: bool             # 声称成功但目标未达
#      false_reject: bool             # 实际达成但被判拒绝
#      detail: dict
```

### 5.1 计划拒绝理由码（本协议希望 #250 提供的最小集合）

| 码 | 触发场景 | 对应 #250 负例类 |
| --- | --- | --- |
| `CONTRACT_CLAIMED_SUCCESS_TARGET_MISSED` | 声称成功但目标场景实测未达 | 声称成功但目标未达 |
| `CONTRACT_GOAL_OR_TOLERANCE_TAMPERED` | `expected_goal` / 容差 / zone 被改 | 目标或阈值被篡改 |
| `CONTRACT_REGRESSION_BROKEN` | 目标过但保留场景失败 | 目标过而回归失败 |
| `CONTRACT_PROTECTED_FILE_CHANGED` | 保护文件 hash 变化 | 保护文件变更 |
| `CONTRACT_EVIDENCE_MISSING` | 证据缺项 | 证据缺失 |
| `CONTRACT_RUN_ID_MISMATCH` | 证据里的 run_id 与本次记录不一致 | run ID 不匹配 |
| `CONTRACT_PASS_WITH_NONZERO_EXIT` | 出现 PASS 文本但进程退出码非 0 | PASS 文本伴随非零退出 |

### 5.2 契约版本化

- 契约文件必须带 `contract_version`；**版本变化即视为新契约**，旧记录的判定不追溯修改。
- 契约的 sha256 在 [ADMISSION.md](ADMISSION.md) 里登记。
- 本协议消费 `reason_codes` 时**只做映射，不改码的含义**（码语义归 #250）。

## 6. 冻结依据（本包引用，不修改）

| 产物 | sha256 | 用途 |
| --- | --- | --- |
| `benchmark/evaluators/evaluate.py` | `441903f15e50555311a9ead9c1426689ad4799294fdc51750c8e276b36279654` | 容差常量与 G1 判定 |
| `benchmark/evaluators/sealed_evaluate.py` | `fa330e69ac6a35aec4b1313638b458885e93c8877ea5dc53f642859783e3acad` | 封存判定入口 |
| `benchmark/schemas/taskspec.schema.json` | `29aae267b157efc2f91d48578ed849c4427e79b629cb3fdea7f892dc7a57563e` | 任务规格结构 |
| `config/run_log_required.json` | `1b0a1c9d93ad3d2425c4109c4dea3726a1d22760b94d73e9dc76b98078ffc291` | 运行日志必需项清单 |

评估器内**声明**的容差（引用，不修改）：

| 常量 | 值 | 语义 |
| --- | --- | --- |
| `HORIZONTAL_TOLERANCE_M` | 0.02 | 水平落点容差 |
| `REST_HEIGHT_TOLERANCE_M` | 0.02 | 静止高度容差 |
| `UNMOVED_TOLERANCE_M` | 0.015 | 「不应移动」容差 |
| zone 半径 | 取自 spec 的 `radius` 字段（示例实例为 0.06） | 是否在区内 |

## 7. 允许与拒绝的修复例子（对照 [PROTOCOL.md](PROTOCOL.md) §7）

| 族 | 候选修复 | 判定 | 依据 |
| --- | --- | --- | --- |
| F1 | 把 B 补回 `tracked_objects` | **允许** | §2.3 允许字段 |
| F1 | 把 B 的尺寸键改对，使 B 被正确注册 | **允许** | §2.3 允许字段 |
| F1 | 扩大 zone_2 半径使 B「算在区内」 | **拒绝** | 目标/阈值篡改 |
| F2 | 把目标区索引改回按决策物体取 | **允许** | §3.3 允许字段 |
| F2 | 把不可达的 zone_2 坐标改近 | **拒绝** | 改 zone 定义（用户目标的一部分） |
| F2 | 在保留场景配置里删掉 `regrasp` | **拒绝** | §4.2 规则 1 + 回归篡改 |
| 任一 | 只改 `task.md` 把目标写简单一点 | **拒绝** | 用户目标不可改 |

## 8. 已知限制

- 缺陷是**人工注入**，本任务族集合不覆盖「自发发现缺陷」。
- F1 与 F2 的修复面不同（配置 vs 源码），**跨族不可直接比较**。
- 保留场景的**具体 spec 与 seed** 由 #253 固定，本包只固定「清单与规则」。
- 注入实现脚本目前不存在，表中标 `TBD` 的字段由 #252 在准入阶段落定。
- §5 的接口是**计划**，在 #250 交付前不可执行；不要把本节的签名当成现有 API。
