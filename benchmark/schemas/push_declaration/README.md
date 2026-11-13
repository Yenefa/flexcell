# #243 — 版本化推动任务声明结构与校验入口

## 为什么需要它

冻结的 `benchmark/schemas/taskspec.schema.json` **从来没有接纳过 T08 的 push 形式**：

| 冻结 TaskSpec 的实际值 | 冻结 canonical schema 的要求 |
| --- | --- |
| `template_id: T08_push_manipulation` | enum 里只有 `T08_push` |
| `expected_goal.push` | 要求 `expected_goal.placement`，且 `additionalProperties: false` |
| `zone_push` | `^zone_[0-9]+$` |
| `instance_sha256` | 顶层 `additionalProperties: false` |

而 `develop/physical-capabilities-20261113` 上的实验探针声明（`89d7eba8` 的 `probe.schema.json`）又是第三种形状（`T08_push` / `0.5.0` / `zone_1`）。**声明格式与消费端脱节**，正是本 issue 要消除的。

## 交付

| 文件 | 作用 |
| --- | --- |
| `v2.schema.json` | 新格式契约，显式 `declaration_version: "2.0"` |
| `v1.schema.json` | **只读的旧格式兼容记录**，忠实描述 12 个冻结 TaskSpec 的真实形状 |
| `validate.py` | 校验入口 + CLI + 显式适配视图，纯标准库 |
| `test_validate.py` | 4 类回归 |

**没有修改**冻结 schema、独立验收器、物理成功阈值、任何历史 TaskSpec 或原始证据。输入文件以 `rb` 只读打开，测试用 SHA256 验证校验前后字节不变。

## 校验命令

```bash
python3 benchmark/schemas/push_declaration/validate.py <declaration.json> [...]
python3 benchmark/schemas/push_declaration/validate.py --json <files>
python3 benchmark/schemas/push_declaration/validate.py --view <legacy.json>
python3 -m unittest discover -s benchmark/schemas/push_declaration -p 'test_*.py' -v
```

退出码：`0` 全部合法 / `1` 存在非法 / `2` 用法错误。输出包含 `status`、`source_format`、`declaration_version`、`problems`、`compat_notes` 和输入文件的 SHA256。

## 兼容范围（明确写出，不隐含）

- **v2**：必须以 `declaration_version: "2.0"` 显式声明；`template_id` 只能 `T08_push`；zone 名 `^zone_[0-9]+$`；不允许 `instance_sha256`。严格校验（缺项、非法值、额外属性、未声明 zone、`min >= max` 一律拒绝）。
- **legacy v1**：无 `declaration_version` 且形状精确匹配 `T08_push_manipulation` + `expected_goal.push` 时，按 `v1.schema.json` 校验，报告 `source_format: legacy_v1`、`version: 1.0 (implicit, legacy)`，并给出兼容说明。
- **v1（显式）**：写了 `declaration_version: "1.0"` 的走同一 v1 契约。
- **缺失版本不提升**：一个没有 `declaration_version`、也不像 legacy 的声明会被判 `unknown` 并**拒绝**。显式写了未知版本同样拒绝。这是 #243 的「不明确兼容范围」防线，避免缺失状态自动变成已验证。
- **split 在 v1 中不是 enum**：12 个冻结任务的真实值是 `train`、`t08_fresh_20261112`、`t08_unseen`。开发中一个猜测的 enum 曾把 `t08_unseen` 误判为非法——v1 忠实记录历史，严格性属于 v2。

## 显式适配，而不是偷偷放宽

`to_v2_view()` 生成一个**只读中间视图**：映射 `template_id`、补 `declaration_version`、从视图中去掉 `instance_sha256`，并把每一处差异列进 `compat_notes`。它：

- **保留原始值**（`zone_push` 不改名，标为 `UNRESOLVED`）
- **不写回任何文件**
- 明确标记 `is_valid_v2: false`——**适配不是验证**，测试里用 `v2` 契约校验这个视图仍会失败

消费端必须自行解决每处差异后才能产出合法 v2 声明。

## 实现边界

`jsonschema` 在本环境不可用，`validate.py` 只实现这两个契约用到的 draft-2020-12 子集（`type/required/additionalProperties/properties/items/enum/const/pattern/minimum/maximum/exclusiveMinimum/minLength/minItems/maxItems/minProperties/maxProperties`），并额外做 schema 无法表达的语义交叉检查。**这是结构校验，不是机器人任务完成能力**：校验通过不表示任务被执行，不提升正式基线，不改变 `CALIBRATION_UNSUPPORTED` 状态。
