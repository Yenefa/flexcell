# 集成测试流程（交付物 7）

**这份文档回答一个问题：拿到一台干净的机器，怎样从零验证 v0.5.0 的证据链是对的。**

分五步，每步都有可观察的期望值。**任一步不符就停下**，不要往下走。

---

## 步骤 0：环境前提

```bash
source /opt/ros/jazzy/setup.bash
source /tmp/t08_iface/install/setup.bash   # 含 PushObject.action 的 overlay
export PYTHONPATH=$WT/src/flexcell/flexcell_skills:$PYTHONPATH   # 追加，不要覆盖
```

**必须追加而不是赋值**：赋值会抹掉 ROS 的 Python 路径，症状是 `No module named sensor_msgs`。
这个错我自己犯过，看起来像代码 bug，实际是环境 bug。

检查：

```bash
python3 -c 'from flexcell_interfaces.action import PushObject; print("ok")'
python3 -c 'from sensor_msgs.msg import Image; print("ok")'
```

两者都要打印 `ok`。

---

## 步骤 1：纯合成层（不需要 Gazebo）

```bash
cd $WT
python3 -m pytest benchmark/evidence/ -q
```

**期望：73 passed。**

这层验证的是判定逻辑本身：8 个强制负例各自按名失败在各自的门上，12 个变异证明删掉任一证据通道都会被拒。

**这层全绿不代表任何机器人做过任何事。**

---

## 步骤 2：评估器集成层（不需要 Gazebo）

```bash
python3 -m pytest benchmark/evidence/test_evaluator_integration.py -q
```

**期望：8 passed。**

这层验证 `evaluate.py` v0.5.0 真的调用了验证器。关键断言：

| 断言 | 为什么重要 |
| --- | --- |
| 终态通过 + 无证据 → `passed=False` | v0.5.0 存在的全部理由 |
| 无证据 → `physical_outcome=UNKNOWN` | 「判断不了」不等于「没推」 |
| 证据完美 + 终态失败 → `passed=False` | 证据是合取，不是覆盖 |
| T01 无 `evidence` 键 | 冻结结果不受影响 |

**这一层最容易静默退化**：验证器测试全绿，而 `evaluate.py` 忘了调用它。

---

## 步骤 3：物理遥测集成（需要 Gazebo，一次）

```bash
pgrep -f 'gz sim' || echo 'channel free'   # 必须为空
bash $CI/evobot_t08_evidence_run.sh
```

**期望产物**（`evidence/` 目录下）：

| 文件 | 检查点 |
| --- | --- |
| `physics_steps_sample.jsonl` | 数千行，非空 |
| `contact_steps_sample.jsonl` | 数千行，含 `component_present: true` |
| `joint_states_sample.jsonl` | 数百行 |
| `evidence_bundle.json` | schema 校验无 problems |

**关键陷阱**：`ContactTrace` 插件**默认不在** `velocity_servo` 后端的世界里。
`sim_profile.py:85` 把它锁死在 `detachable_joint` + 2ms。
证据脚本通过**在生成的 world 副本上注入插件**绕开这一点，不改 `sim_profile.py`。

验证插件真的进去了：

```bash
grep -c 'ContactTrace' $OUT/sim/world.sdf   # 期望 >= 1
```

**期望：接触行数 > 0。若为 0，说明注入失败，不是机器人没接触。**

---

## 步骤 4：端到端判定（真实证据喂给真实评估器）

```bash
python3 benchmark/evaluators/evaluate.py \
  benchmark/tasks/t08_dev/T08-push-seed2000.json \
  /tmp/v5/real.json
```

`/tmp/v5/real.json` = `{objects: <gt_after>, evidence: <evidence_bundle>}`。

**期望输出结构**：

```json
{
  "evaluator_version": "0.5.0",
  "passed": false,
  "terminal_passed": false,
  "failed_clauses": ["push:target_box_a"],
  "evidence": {
    "physical_outcome": "UNKNOWN",
    "evidence_status": "INCOMPLETE_OR_INVALID_EVIDENCE",
    "gates": [ ... 每门一行 ... ]
  }
}

```

**注意 `terminal_passed` 与 `passed` 是两个字段**。它们分开是有意的：
前者说「终态几何合不合格」，后者说「任务算不算完成」。

---

## 步骤 5：读结论时必须区分的四层

| 层 | 由什么证明 | 不能推出什么 |
| --- | --- | --- |
| **L1 合成验证器验证** | 步骤 1、2 全绿 | 机器人没做过任何事 |
| **L2 物理遥测集成** | 步骤 3 产出真实行 | 任务完成 |
| **L3 Gazebo 实推验证** | 步骤 4 里各门的具体值 | 任务验收通过 |
| **L4 独立任务验收** | `passed=true` | 泛化能力 |

**当前实际状态**：L1 ✅ L2 ✅ L3 ✅（8/9 门） **L4 ❌**（23.26 mm < 30 mm）。

---

## 已知会让这套流程误报的环境问题

| 症状 | 真因 | 处置 |
| --- | --- | --- |
| `No module named sensor_msgs` | `PYTHONPATH` 被赋值而非追加 | 改用 `:$PYTHONPATH` |
| `No module named flexcell_interfaces` | 未 source overlay | source `/tmp/t08_iface/install` |
| `FileExistsError: params.yaml` | 残留 `sim/` 目录 | 脚本已加 `rm -rf $OUT/sim` |
| 接触行数为 0 | 插件没注入 | 检查 world.sdf 里有没有 `ContactTrace` |
| `more than one action server` | 上次运行残留 server | `pkill -9 -f push_server` |
| 轨迹文件不存在 | 跟踪器被 SIGINT 杀掉 | 它只在循环结束后写文件，必须 `wait` |

最后两条都是我在真实运行中踩过的，不是假设。

---

## 一次完整验证的最短路径

```bash
cd $WT
python3 -m pytest benchmark/evidence/ -q                    # 73 passed
bash $CI/evobot_t08_evidence_run.sh                         # 产出真实证据
python3 benchmark/evaluators/evaluate.py $T08 /tmp/v5/real.json
```

三条命令，约 10 分钟（含一次 Gazebo 启动）。
