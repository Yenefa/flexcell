# A：机器人动作技能目录与适用条件查询

优先级 P1；第一步 D1，完整模块 D2。目标是让执行 Agent 能查询“有哪些动作、接口是什么、
适用条件与证据范围是什么”。本模块只返回声明，不判断现场物理可行性，不派发动作。
这里的技能目录描述机器人动作接口；任务方法 Skill 的生成不属于此首版。

分支：`feat/runtime-skill-catalog-20261116`。PR base：`chore/team-handoff-20261116`。
认领与提交关联：[issue #245](https://github.com/Yenefa/flexcell/issues/245)。

## 独占修改范围

- `runtime/skill_catalog/`：新增纯模块、CLI、模块内测试。
- `config/skill_catalog/`：目录数据，第一条是交接中的 ContactPush 示例。
- `docs/SKILL_CATALOG.md`：使用说明和范围。

现有 `runtime/planner/push_task.py`、`runtime/run_public_push_task.py`、ROS 服务、接口、
`flexcell_capabilities` 与验收器继续由主线维护，本 PR 不改在线调用链。

## 首个 PR：先做一个完整的小功能

实现加载目录、按 ID 获取记录、列出记录；以 `schema_version` 明确格式版本。
建议 API：`load_catalog(path)`、`list_skills(catalog)`、`get_skill(catalog, skill_id)`。
加载或查询不修改传入对象；无效输入用明确异常/错误码返回。
`load_catalog` 返回校验后的顶层字典，`list_skills` 返回记录列表，`get_skill` 返回一条记录或
抛出 `KeyError`。CLI 的 list 输出包含 `declaration_only: true` 和 `skills`，get 输出包含
`declaration_only: true` 和 `skill`；错误输出含明确 `error` 与 `reason`，不能混入成功列表。

```bash
python3 -m runtime.skill_catalog list --catalog config/skill_catalog/contact_push.example.json
python3 -m runtime.skill_catalog get --catalog config/skill_catalog/contact_push.example.json \
  --id contact_push.finger_tcp.v1
python3 -m unittest discover -s runtime/skill_catalog/tests -v
```

这三个是待实现的验收入口，目前没有目录实现。
CLI：成功查询退出 0；ID 不存在退出 1；JSON/结构/版本错误退出 2。

## 数据契约

输入示例：`config/skill_catalog/contact_push.example.json`。必须包含：

- 顶层：`schema_version`、`skills`。
- 每条记录：唯一 `id`、`kind`、`interface`、`implementation_state`、`availability`、
  `default_enabled`、`parameter_constraints`、`preconditions`、`limitations`、`validation`。
- `validation`：`level`、`executed_source_commit`、`evidence_ref`；缺来源时只能写 UNKNOWN。
- 已登记状态：`IMPLEMENTED` / `PROPOSED` / `UNKNOWN`；可用性：`OPT_IN` / `UNAVAILABLE` / `UNKNOWN`。
- 查询输出原样保留状态和范围；候选不能因为进入目录就变成可调用、已验证或默认启用。

示例记录是手工整理的单条声明，尚未接入 Runtime。核对来源：

1. `src/flexcell/flexcell_interfaces/action/ContactPush.action`：请求/返回格式。
2. `src/flexcell/flexcell_skills/flexcell_skills/contact_push_server.py` 的 `validate_request`：
   已登记的是世界 −x、单次 30mm、`demo_veryslow`，目录不能扩成任意方向和距离。
3. `setup/acceptance/physical_reachable_contact_20261113/archive.json`、README：限定仿真证据，
   default legacy、正式基线未晋升。查询时不执行验收器或加载原始日志。

## 必须可复核的情况

- 合法目录可 list/get；重复 ID、缺关键字段、未知版本、损坏 JSON 都明确失败。
- 不存在 ID 有明确结果；空目录明确为空，不生成默认技能。
- 非有限数字拒绝；输出为标准 JSON，不出现 NaN/Infinity。
- PROPOSED、UNKNOWN、OPT_IN、default=false 在输出中保持原义。
- 输入文件运行前后 SHA-256 不变；从无 ROS 环境可导入、查询和测试。

首个 PR 通过后，才讨论筛选、参数声明检查和 Runtime 接入；自动规划、现场可行性判断、
新动作实现与效果提升不计入此任务。

可复制给开发者：

> 在分支 feat/runtime-skill-catalog-20261116 开发动作技能目录，完整遵守本文件范围。
> 先读 ContactPush 接口、请求校验和示例元数据，实现 list/get 和明确错误处理，补齐上述
> 正常与失败情况。不要改动作实现、规划器或验收规则；提交 PR 到 chore/team-handoff-20261116。
