# T08 轨迹证据验证器：版本化验收报告

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-12 |
| 执行者 | skill-gap（teammate） |
| 验证器版本 | **1.0.0** |
| 证据 schema 版本 | **t08-evidence/1.0** |
| 终态评测器 | **v0.4.0 → v0.5.0**（本轮集成，见下） |
| v0.4.0 行为 | **未放宽任何阈值**；v0.5.0 只做合取，只能把 pass 变 fail |
| v0.3.0 | **未改**（与 HEAD 逐字节相同） |
| 30 mm 阈值 | **未改** |
| TaskSpec | **未改** |
| PushObject 技能实现 | **未改**（与 HEAD 逐字节相同） |
| `sim_profile.py` | **未改**（与 HEAD 逐字节相同） |
| git commit | 验证器 `2f90a58a`；v0.5.0 集成 `879d8d82`；集成流程 `d1720049` |
| LLM 调用 | 0 |

---

## 0.1 v0.5.0 集成（本报告初稿之后补做，必须单列）

本报告初稿写于验证器单独成立时，当时**终态评测器仍是 v0.4.0 且从不调用验证器**。
一个没人调用的验证器等于一份文档，所以补了集成。

| 项 | 集成前 | 集成后 |
| --- | --- | --- |
| 评测器版本 | v0.4.0 | **v0.5.0** |
| 是否调用 `verify()` | ❌ 从不 | ✅ push 任务必调 |
| 无证据包时 | 只看终态 | **fail closed** |
| T01–T06 | 不受影响 | **不受影响**（有测试断言） |

### 决定性用例（v0.4.0 表达不出来）

```
terminal_passed = True      终态几何完全合格
failed_clauses  = []        没有子句失败
passed          = False     仍然判失败
evidence_status = INCOMPLETE_OR_INVALID_EVIDENCE
```

### 三个变异证明集成会咬

| 变异 | 被捕获于 |
| --- | --- |
| 忽略 `verify()` 返回值 | `test_a_malformed_bundle_fails_closed` |
| 缺失证据当成通过 | `test_the_terminal_state_alone_is_no_longer_enough` |
| 证据要求泄漏到 T01–T06 | `test_t01_has_no_evidence_requirement_and_keeps_its_old_shape` |

### 集成后抓到并修复的一个接线缺陷（本报告必须记录）

集成完成后，把**有效证据包**穿过真实调用路径，与直接 `verify()` 对比，得到两个不同答案：

```
verify(bundle, terminal, fixtures.limits())  ->  PUSHED,  COMPLETE,  passed=True
verify(bundle, terminal)   <- evaluate.py    ->  NOT_PUSHED, passed=False
```

**根因**：三个门是限值依赖的，拿到 `None` 时各自 `return False, "no lift limit supplied"`。
这对门是对的，对调用方是灾难——`evaluate.py` 一个 limits 都没传。
**每一次真实推都会被判成 NOT_PUSHED。**

**为什么测试看不见**：单元测试用 `judge()` 传了 `fixtures.limits()`，集成测试也是，
而唯一的真实调用路径没传。**65 个验证器测试全绿 + 8 个集成测试全绿，与「生产路径每次都失败」并存。**

**修复**：`evaluate.py` 从同一个 spec 推导限值，证据层与终态层不可能对任务产生分歧。

**修复前后的真实证据包对比**：

| 门 | 修复前 | 修复后 |
| --- | --- | --- |
| no_lift | FAIL（无上限） | **OK** |
| gripper | FAIL（无上限） | **OK** |
| terminal | FAIL（23.26 mm） | FAIL（23.26 mm） |
| 其余 6 门 | OK | OK |

**所以本报告此前写的「8/9 门通过」在修复前是错的**（实际是 6/9），
现在才真正成立。这不是证据变了，是判据的接线修好了。

---

### 30 mm 阈值被测试钉死

`test_the_30mm_threshold_is_untouched` 断言 `min_displacement_m == 0.030`。
连续三次失败（23.02 / 28.55 / 23.26 mm）正是最想改它的压力点。

---

## 0. 四层分离（本报告的核心纪律）

本任务的所有结论必须分四层读，**不同层之间不可互相冒充**：

| 层 | 含义 | 本卡状态 | 允许的措辞 |
| --- | --- | --- | --- |
| **L1 合成验证器验证** | 用合成 fixture 证明 9 个证据门各自可独立拒绝 | ✅ **已完成**，65 测试 | "验证器在合成证据上按设计拒绝/通过" |
| **L2 物理遥测集成** | 真实 Gazebo 插件 step log → recorder → schema 合法 bundle | ✅ **已完成**，3210 步真实数据 | "真实物理遥测能被读成合法证据包" |
| **L3 实际 Gazebo 推验证** | 一次真实推，用真实遥测跑完 9 门 | ✅ **已完成**，8/9 通过 | "这次真实推的物理证据完整且指向'推了'" |
| **L4 独立任务验收** | T08 判定通过 | ❌ **未达成**，位移 23.26 mm < 30 mm | **不宣称** |

**L3 通过而 L4 不通过是正确结果，不是缺陷。** 技能确实饱和在 30 mm 门槛之下；
本卡不调阈值、不解释掉这个差距。物理证据层说"这是一次真实的、有接触的、没抬起的推"，
终态判据说"但它只走了 23.26 mm"。两句话同时为真。

---

## 1. 审计补充：发现一个审计未提及的关键缺口

审计文档说 `ContactTrace.cc` "是你的接触证据源"。**实测它不在 T08 推所用的世界里**：

```
T08 推后端          : velocity_servo
PhysicsTrace 在世界里: True
ContactTrace 在世界里: False      <-- 接触证据源缺失
contacts_entity_names: False      <-- 推杆身份所需的碰撞体命名也缺失
```

原因在 `sim_profile.py:85`：

```python
if contact_trace and (backend != 'detachable_joint' or physics_step_s != .002):
    raise ValueError('integrated contact trace requires the declared 2 ms joint profile')
```

**处理方式：不改 `sim_profile.py`。** 它生成的 world 被 `world_sha256` 冻进声明里，
改它会静默改写历史证据。改为在**生成的 world 副本上注入** ContactTrace 插件与
`contacts_entity_names`（见 §4）。`sim_profile.py` 与 HEAD 逐字节相同，已验证。

这是本卡对审计的最实质补充：**审计给出的证据源本身没有接进被测世界。**

---

## 2. 交付物

| # | 文件 | 作用 |
| --- | --- | --- |
| 1 | `ARCHITECTURE_AUDIT.md` | 已有（本卡补充了 §1 的缺口） |
| 2 | `benchmark/evidence/recorder.py` | 从插件 step log 读 6-DOF 轨迹 → 证据包 |
| 3 | `benchmark/evidence/schema.py` | 证据 schema + fail-closed 校验 |
| 4 | `benchmark/evidence/verify.py` | **fail-closed 验证器 v1.0.0**（9 门） |
| 5 | `benchmark/evidence/test_verifier.py` | 8 个强制负例 + 12 个变异 + 边界 |
| 6 | `benchmark/evidence/test_recorder.py` | recorder 单测（含真实归档 contact log） |
| 7 | `benchmark/evidence/fixtures.py` | 可复现合成正/负 fixture |
| 8 | `ci-public-window/scripts/evobot_t08_evidence_run.sh` | 真实 Gazebo 证据采集 |

---

## 3. 验证器设计：9 个证据门

每一门回答别门回答不了的问题，**任一失败即整体失败**，不求和、不计分。

| # | 门 | 判据 | 为什么单独存在 |
| --- | --- | --- | --- |
| 1 | `terminal` | 冻结终态子句通过 | 物理层不得绕过终态判据 |
| 2 | `trajectory` | schema 全合法 | 格式坏了下面全部无意义 |
| 3 | `table_support` | 目标全程贴桌 | 与 `no_lift` 不同：**持续悬空**也是搬运 |
| 3b | `protected_unmoved` | 保护物体未被扰动 | T08 明令禁止动蓝块 |
| 4 | `no_lift` | 全程最大高度 ≤ 限 | 抬起又放回，只有 max 看得见 |
| 5 | `pusher_contact` | 声明的推杆 link 有接触**且与位移重叠** | 接近≠接触；接触≠因果 |
| 6 | `gripper` | 孔径**变化量** ≤ 限 | 抓取是孔径**运动**，不是孔径值 |
| 7 | `no_attachment` | 无 DetachableJoint 事件 | 物理直证，非几何推断 |
| 8 | `no_teleport` | 单步跳变 ≤ 限（**从样本实测**） | 被外部改位姿与推无法区分 |

### 三字段输出

```json
{"physical_outcome": "PUSHED|NOT_PUSHED|UNKNOWN",
 "evidence_status":  "COMPLETE|COMPLETE_EVIDENCE_CONTRADICTS_PUSH|INCOMPLETE_OR_INVALID_EVIDENCE",
 "failure_reason":   "...|null"}
```

**"机器人没推" 与 "我们无法判断机器人是否推了" 必须分开。** 前者是机器人问题，
后者是测量问题；合并二者正是"遥测缺失被报成机器人失败"的成因。

---

## 4. L2：真实物理遥测集成

```bash
bash ci-public-window/scripts/evobot_t08_evidence_run.sh <out> <task> 0.030 47
```

流程：生成 velocity_servo world → **在副本上注入** ContactTrace + `contacts_entity_names`
+ 接触传感器 → 设 `FLEXCELL_CONTACT_STEP_LOG` / `FLEXCELL_PHYSICS_STEP_LOG` → 启动 →
订阅 `/joint_states` → 派发真实 push → 收证据。

实测产出：

```
evidence_bundle.json   内嵌 3210×2 完整样本（1.47 MB，可复核）
contact_steps_sample.jsonl   200 行（预览切片；全量在 bundle 内）
physics_steps_sample.jsonl   200 行（预览切片；全量在 bundle 内）
joint_states_sample.jsonl    100 行（预览切片；全量 937 在 bundle 内）

**归档说明**：`_sample.jsonl` 是为便于人眼查看而截取的预览，**不是全量证据**。
全量样本内嵌在 `evidence_bundle.json` 的 `objects.*.samples` 里，验证器读的是后者。
引用行数时必须以 bundle 为准，否则会误以为证据被截断。
```

recorder 读出的 bundle：

```
target_box_a   role=target      samples=3210  dropped=0  max_gap=5000000 ns
target_box_b   role=protected   samples=3210  dropped=0  max_gap=5000000 ns
contacts: component_present=True   intervals=4
attachment: attached=False  events=0
teleport: max_jump=0.00055545 m
gripper: joint=gripper_left_joint  span=937  min=-0.000001  max=0.000000
schema problems: NONE
```

**真实接触伙伴**（这是推杆身份的经验依据，不是猜的）：

```
ground_plane::link::collision
open_manipulator_x::gripper_left_link::gripper_left_link_collision
open_manipulator_x::gripper_right_link::gripper_right_link_collision
target_box_a::link::col
```

推杆 = `gripper_left_link` / `gripper_right_link`。桌面也在伙伴里——这正是
`pusher_contact` 必须**指名**推杆 link 的理由：否则"接触"永远为真（物体一直躺在桌上）。

---

## 5. L3：真实 Gazebo 推验证结果

同一次真实推（`contact_height_m=0.030`，请求 90 mm）：

```
=== 终态（冻结 v0.4.0）===
  passed: False   failed: ['push:target_box_a']
  displacement_m = 0.02326   （门槛 0.03）
  direction_cosine = 0.9997
  vertical_m = 0.0

=== 证据验证器 v1.0.0 ===
  [FAIL] terminal         终态未通过（位移 23.26 mm < 30 mm）
  [PASS] trajectory       3210×2 样本，0 丢弃，间隙 5 ms
  [PASS] table_support    全程贴桌
  [PASS] protected_unmoved 蓝块零位移
  [PASS] no_lift          最大离桌高度 ≈ 0
  [PASS] pusher_contact   4 段真实推杆接触，与位移重叠
  [PASS] gripper          孔径变化 ≈ 0
  [PASS] no_attachment    0 事件
  [PASS] no_teleport      最大单步 0.00056 m
```

**8/9 通过，唯一失败的是冻结的 30 mm 位移子句。**

对照实验（只把终态改成通过，其余数据一字不改）：

```
physical_outcome: PUSHED
evidence_status : COMPLETE
passed          : True
```

**这说明物理证据层本身不阻碍 T08。** 挡住它的是技能真实饱和（23–28.5 mm），
而阈值是冻结的，本卡不调。

---

## 6. 真实运行抓到的两个设计缺陷（合成测试抓不到）

### 6.1 teleport 门信任了声明值
原实现读 `bundle["teleport"]["max_single_step_jump_m"]`。证据包可以声明 5 mm
而自己的样本里有 80 mm 跳变——**声明会赢**。已改为**从样本实测**，
声明与实测不符本身也判失败。

### 6.2 teleport 门把两个物体拼在一起算
拼接两个物体的样本会凭空产生"从 A 最后一点到 B 第一点"的跳变，
两个相距 4.8 m 的箱子被算成 4.8 m teleport，**所有正常 run 都被拒**。
实测报错：`4.8050 m exceeds 0.0300 m`。已改为**逐物体**计算。

### 6.3 夹爪门把"非抓取"当成"张开"（真实遥测证伪）
合成 fixture 里我假设非抓取=张开，于是要求孔径 **高于** 阈值。
真实遥测推翻了这个假设：**这台机器人是闭着手指推的**，937 个关节样本孔径全 ≈ 0.000 rad。
一个"必须张开"的门会拒掉**每一次真实推**——这是"通过一切"的镜像缺陷。

已改为判**孔径变化量**：抓取意味着手指闭合**到物体上**，孔径会变；推是恒定孔径。
另有 `no_attachment` 门独立排除物理连接。

> 这条只有真实遥测能发现。合成 fixture 由我自己的假设写成，只会与我的假设一致。

### 6.4 保护物体完全没有被判
变异测试发现：把蓝块推走 20 mm 能通过全部 8 门。**轨迹被采集却从未被读。**
已补 `protected_unmoved` 门（含"推走又推回"仍判失败，因为看最大偏移）。

---

## 7. 测试

| 套件 | 数量 |
| --- | --- |
| `test_verifier.py`（8 强制负例 + 12 变异 + 边界） | 45 |
| `test_recorder.py`（含真实归档 contact log） | 20 |
| **本卡合计** | **65 全绿** |
| 全仓技能套件 + 证据套件 | **1373 / 1373，0 failed** |

**8 个强制负例全部按名断言失败门**，不是只断言 `passed=False`——
否则"格式坏了"会冒充"检测到抬起"。

| # | 负例 | 失败门 |
| --- | --- | --- |
| 1 | 有效 40 mm 推 | **PASS**（阳性对照） |
| 2 | 抬起、搬运、放回原高度 | `no_lift`（+ `table_support`） |
| 3 | 恒定高度搬运 | `table_support`（+ `no_lift`） |
| 4 | 抬起 25 mm 放回 | `no_lift` |
| 5 | 物体移动但无推杆接触 | `pusher_contact`（3 个变体） |
| 6 | 轨迹缺失 | `trajectory`（3 个变体） |
| 7 | 轨迹截断/不连续 | `trajectory`（5 个变体） |
| 8 | 直接 teleport | `no_teleport`（4 个变体） |

变异测试：12 个"移除一个必需通道"的变异**全部被拒**，且失败签名不全相同
（证明没有单一门在做全部工作）。

---

## 8. 复现

```bash
# L1 合成验证器验证
cd wt-comp/benchmark/evidence && python3 -m pytest -q

# L2+L3 真实采集与判定
bash ci-public-window/scripts/evobot_t08_evidence_run.sh /tmp/t08ev \
  wt-comp/benchmark/tasks/t08_dev/T08-push-seed2000.json 0.030 47
python3 - <<'PY'
import sys; sys.path.insert(0, 'wt-comp/benchmark/evidence')
import recorder, verify, json
from pathlib import Path
EV = Path('/tmp/t08ev')
args = type('A', (), dict(
    physics_log=str(EV/'logs'/'physics_steps.jsonl'),
    contact_log=str(EV/'logs'/'contact_steps.jsonl'),
    joint_log=str(EV/'logs'/'joint_states.jsonl'),
    task='wt-comp/benchmark/tasks/t08_dev/T08-push-seed2000.json',
    task_id='T08-push-seed2000', run_id='r1',
    target='target_box_a', protected='target_box_b', rest_height=0.0175,
    pusher_links=['open_manipulator_x::gripper_left_link::gripper_left_link_collision'],
    gripper_joint='gripper_left_joint'))()
print(verify.verify(recorder.build(args),
      {'passed': True, 'evaluator_version': '0.4.0'},
      {'max_lift_during_m': .005, 'max_aperture_change_rad': .002,
       'protected_move_m': .005})['evidence_status'])
PY
```

---

## 9. 明确不宣称

- **不宣称 L4（独立任务验收通过）。** 位移 23.26 mm < 30 mm，T08 未通过。
- **不宣称技能变好了。** 本卡一行技能代码没改。
- **不宣称阈值应该改。** 30 mm 冻结，本卡不调。
- **不宣称视觉是主判据。** 视觉在本卡中完全不参与物理判定；物理遥测才是。
- **不宣称合成测试等于物理验证。** L1 与 L3 是不同层，本报告分开写。
- 不宣称任何 rung 提升。L1+L2+L3 已做，L4 未达成。

---

## 10. 残留限制（诚实清单）

1. **推杆 link 是经验确定的**，不是配置声明的。目前从真实接触伙伴反推
   （`gripper_left_link`/`gripper_right_link`）。理想做法是在 world 里显式声明
   推杆 link 身份，本卡未做（会改 world 生成）。
2. **`rest_height_m` 由调用方传入**（0.0175），不是从证据推断的。
   传错会让 `table_support`/no_lift 判错。
3. **物理步长 5 ms**，不是 contact_trace 要求的 2 ms。3210 步覆盖整段推，
   但亚 5 ms 的瞬态抬起不可见。
4. **单次真实运行**。n=1，不是成功率。
5. 证据包的 `bundle_sha256` 防篡改，但**未签名**；能发现改动，不能证明来源。