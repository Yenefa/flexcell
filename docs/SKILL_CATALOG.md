# 机器人动作技能目录（issue #245，首个 PR）

一个**只返回声明**的查询模块：让执行 Agent 知道"有哪些动作、接口是什么、适用条件和证据范围是什么"。
它不判断现场物理可行性、不派发动作、不连接 Online Runtime，也不修改控制器、规划器或验收规则。
任务方法 Skill 的生成不属于此首版。

## 命令

在仓库根目录执行：

```bash
python3 -m runtime.skill_catalog list --catalog config/skill_catalog/contact_push.example.json
python3 -m runtime.skill_catalog get --catalog config/skill_catalog/contact_push.example.json \
  --id contact_push.finger_tcp.v1
python3 -m unittest discover -s runtime/skill_catalog/tests -v
```

成功输出为标准 JSON，`list` 含 `declaration_only: true` 与 `skills`，`get` 含
`declaration_only: true` 与 `skill`。错误输出为单独的 JSON 对象，含明确的
`error` 与 `reason`，不会混进成功列表。

| 退出码 | 含义 |
| --- | --- |
| 0 | 查询成功 |
| 1 | ID 不存在（`SkillNotFound`） |
| 2 | JSON 损坏、版本不支持、结构/字段不合法或参数缺失（`CatalogError`） |

## Python 接口

```python
from runtime.skill_catalog import load_catalog, list_skills, get_skill

catalog = load_catalog("config/skill_catalog/contact_push.example.json")
skills = list_skills(catalog)                      # 独立副本
skill = get_skill(catalog, "contact_push.finger_tcp.v1")  # 独立副本，找不到抛 KeyError
```

`load_catalog` 返回校验后的顶层字典；加载与查询都不修改传入对象，也不修改输入文件。

## 数据契约

顶层必须含 `schema_version: "skill-catalog/1"` 和 `skills` 数组。每条记录必须含：

`id`（唯一）、`kind`、`interface`、`implementation_state`、`availability`、
`default_enabled`、`parameter_constraints`、`preconditions`、`limitations`、`validation`。

- `implementation_state` 只允许 `IMPLEMENTED` / `PROPOSED` / `UNKNOWN`
- `availability` 只允许 `OPT_IN` / `UNAVAILABLE` / `UNKNOWN`
- `validation` 含 `level`、`executed_source_commit`、`evidence_ref`；缺来源写 `UNKNOWN`，不猜值
- 非有限数字（NaN / Infinity / 1e999）、重复 ID、缺关键字段、未知版本一律明确失败

## 语义边界（重要）

- 进入目录**不等于**可调用、已验证或默认启用：`PROPOSED`、`UNKNOWN`、`OPT_IN`、`default_enabled=false`
  在输出中保持原义，查询层不做升级、筛选或解释。
- ContactPush 示例只登记世界 −x 单次 30 mm、`demo_veryslow` 的有界原语，不扩成任意方向或距离。
- 证据只指向已归档的仿真记录；默认后端仍是 legacy，正式基线 **NOT_PROMOTED**。
- 查询时不执行验收器、不加载原始日志、不导入 ROS；无 ROS 环境可导入、查询和测试。

## 与源码的核对（2026-11-17）

示例记录的每个值都能在仓库里找到出处，不靠推测：

| 目录里的声明 | 出处 |
| --- | --- |
| `interface: flexcell_interfaces/action/ContactPush` | `src/flexcell/flexcell_interfaces/action/ContactPush.action` 的请求段（`direction`、`distance_m`、`motion_profile_id`、`deadline_ms`、`max_motion_goals` 等） |
| `direction.const = [-1, 0, 0]` | `contact_push_server.py` 的 `validate_request`：方向不等 `[-1,0,0]` 直接拒 |
| `distance_m.const = 0.03` | 同上：`abs(distance_m - .03) > 1e-12` 直接拒 |
| `motion_profile_id.const = demo_veryslow` | 同上：其余档位一律拒 |
| `preconditions` 第三条「Motion budget and request fields…」 | 同上的 `deadline_ms <= 300000`、`max_motion_goals ∈ {0} ∪ [13,40]`、`preserve_objects` 不得重复 |
| `validation.level = SCOPED_SIMULATION`、`evidence_ref` | `setup/acceptance/physical_reachable_contact_20261113/` 的 `archive.json` 与 README；默认后端 legacy、正式基线 NOT_PROMOTED |

`parameter_constraints` 只登记已经实现并演练过的几何原语（世界 −x、单次 30 mm、`demo_veryslow`），
其余准入条件写在 `preconditions` 里。目录**不做**参数合法性判断，也不替动作服务器做准入——
按交接文档，参数声明检查属于首个 PR 通过之后的范围。

## 验证记录

`python3 -m unittest discover -s runtime/skill_catalog/tests -v` 共 10 例，覆盖：
合法目录 list/get、ID 不存在、重复 ID、缺字段与非法枚举、未知版本、损坏 JSON、
非有限数字、空目录、状态原义保留、输入 SHA 不变且返回对象彼此独立、CLI 四种退出码与输出形状。
