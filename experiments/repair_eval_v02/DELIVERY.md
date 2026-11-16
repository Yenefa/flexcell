# 交付说明（#249–#254，截至 2026-11-17）

这份文件回答一个问题：**拿到这五个分支，怎么在十分钟内确认它们是真的。**

## 1. 分支与内容

| issue | 分支 | 内容 | 测试 |
| --- | --- | --- | --- |
| #249 | `codex/evobot-paper-v02-visibility` | `benchmark/repair_eval/visibility.py` + 策略 JSON + 61 条测试 | 可见性边界：四条件下谁能读什么，读不到要拒绝并留痕 |
| #250 | `codex/evobot-paper-v02-task-contract` | `contracts/task_contract.py`、`acceptance.py`、`casefile.py` + 132 条测试 | 契约/验收：可编辑面、判定规则、case 文件 |
| #251 | `codex/evobot-paper-v02-protocol` | `PROTOCOL.md` v0.1.3、`RUN_MANIFEST.md`、`ANALYSIS.md`、自检脚本 | 协议自检：文档形状、判决封印、计数与行一致 |
| #252 | `codex/evobot-paper-v02-control-runs` | 执行器、成本闸、真实例、跑批器、证据、v2 题面 | 见下 |
| #253 | 同 #252 | `holdout.py` + 6 槽端到端演练 | 冻结、四道拒绝、计数分离 |
| #254 | `codex/evobot-paper-v02-paper` | `CLAIMS_EVIDENCE_TABLE.md`（R1/R2/R3）、`METHOD.md`、`HISTORY` | 结论表每行可追溯到证据文件与身份字段 |

## 2. 十分钟验收

```bash
# 1) 五分支合并（在任意干净基线上）
for b in visibility task-contract protocol paper control-runs; do
  git merge --no-edit origin/codex/evobot-paper-v02-$b
done

# 2) 全量测试
python3 -m pytest benchmark/repair_eval experiments/repair_eval_v02 -q
# 期望：342 passed

# 3) 三份自检
python3 experiments/repair_eval_v02/crosscheck_docs.py      # documents and code agree
python3 docs/research/evobot-paper-v02/check_protocol_docs.py  # PASS
python3 experiments/repair_eval_v02/audit_acceptance.py     # 46/46, 0 UNMET

# 4) 两个实例的可判别性（不花 token）
python3 experiments/repair_eval_v02/dry_run_instances.py
python3 experiments/repair_eval_v02/dry_run_instances_scripted.py
# 期望：defect injected -> FAIL, repaired -> PASS, discriminates=True

# 5) 保留场景的锁（不花 token）
python3 experiments/repair_eval_v02/dry_run_holdout.py   # exit 0, ok=true

# 6) 对账
python3 experiments/repair_eval_v02/reconcile.py \
  --manifest docs/research/evobot-paper-v02/RUN_MANIFEST.md \
  --records experiments/repair_eval_v02/evidence/real_instances_matrix.json
# 期望：verdict CONSISTENT（24 槽 / 24 记录 / 0 排除）
```

## 3. 已经跑出来的结果

`evidence/real_instances_matrix.json`：24 槽真实例，144,133 tokens，22 槽门判 `PASS`。
按条件看（`summarise.py` 生成，已标注截断）：

```
fam condition                n   PASS cen/cap mean_int
F1  A_STATIC                 3      3    0/0     3.00
F1  B_REAL_FEEDBACK          3      3    0/0     3.00
F1  C_MISMATCHED_FEEDBACK    3      3    0/0     2.67
F1  D_GUIDED                 3      3    1/1     4.33
F2  A_STATIC                 3      3    3/3     6.00   <- all at cap
F2  B_REAL_FEEDBACK          3      1    3/3     6.00   <- all at cap
F2  C_MISMATCHED_FEEDBACK    3      3    1/1     4.33
F2  D_GUIDED                 3      3    0/0     4.33
```

**这些数不能当条件效应读**，原因写在 `DEFECT_DESIGN.md` 与 `ANALYSIS §6.01`：F1 的答案就在题面里、交互数被上限截断、n=3 且单格重跑会变号。

## 4. 三批被作废的数据（保留可查）

| 文件 | tokens | 作废原因 |
| --- | --- | --- |
| `real_instances_matrix_writeonly_INVALIDATED.json` | 187,741 | 只有整文件重写接口，模型把 1578 行节点换成 18 行存根 |
| `budget_matrix_static_INVALIDATED.json` | 80,778 | 校验和静态反馈混淆，B/C/D 退化成 A |
| `budget_matrix_interference_INVALIDATED.json` | 41,131 | 每步反馈走合成 pytest，覆盖了门的类型化答案 |

三批都保留而不是删除：它们记录的是测试台的故障模式，删掉会让后来人重复踩。

## 5. 没做完的与原因

| 未完成 | 阻塞原因 |
| --- | --- |
| 四条件主对比（可解读版） | 需切到 `--task-variant v2`（作废现有 24 槽）+ 约 48 万 tokens 额度 |
| 保留场景的真实运行 | 需真实例的 layout/state 变化（设计工作）+ 额度 |
| 独立裁决门（G3） | 需在保留场景上运行；未运行前所有终态只能记 `UNKNOWN` |
| 论文的作者/单位/授权声明 | 需人填，非技术项 |

## 6. 一句话总结

**机制全部落地并验证过；效应量没有测出来，因为第一版题面把答案写在了题目里，且样本量不足。**
补齐这两点需要一次约 48 万 tokens 的重跑，代码已就绪（`--task-variant v2`）。

## 7. 主批次与最终状态（2026-11-17 更新）

### 已经跑出来的主结果

`evidence/v2_matrix_n6.json`：**48 槽，535,151 tokens**，题面切到 `task_variant=v2`（不写答案），每格 6 次重复。

| 族 | A 无反馈 | B 真实反馈 | C 失配反馈 | D 真实+指导 |
| --- | --- | --- | --- | --- |
| F1 | 6/6 | 6/6 | 6/6 | 6/6 |
| F2 | 2/6 | 2/6 | 3/6 | 4/6 |

**这是一个零结果**：F1 全过（配置键名 `object_target_box_a_size` 本身就给出物体名，静态输入对所有条件可见）；
F2 的四条件成功率最大对比（A 对 D，2/6 对 4/6）Fisher 精确检验 **p = 0.57**，不能拒绝「四条件相同」。
成本有差异但不单调（F2 平均 tokens：A 22,739 / B 15,542 / C 17,316 / D 13,484）。

### 本轮修掉的三个真缺陷

1. **删除即通过**：配置不写 `tracked_objects` 时门回落到节点默认值（恰好是健康值），于是删掉那行就能过。新增 `TRACKED_OBJECTS_ABSENT`。
2. **v2 试点的参数错误**：`--families` 收族名而非实例名，错传导致跑了错实例、烧掉 63,460 tokens。现在立即失败并提示合法值。
3. **记录字段与文档不一致**：`task_variant` 原先事后塞进记录，文档声明了但记录没有。改为 `build_record` 的正式参数。

### #253 现在有真实差异

两个 layout（区位坐标不同）× 三个 state。定向修复在 L1/L2 都通过；**写死坐标的修复在 L2 被抓**（`LAYOUT_VALUES_CHANGED`）。
参考修复也据此改为只替换出错那一行——整文件重写会悄悄回退另一个 layout。

### 明确没做的

| 项 | 状态 |
| --- | --- |
| 独立裁决门（G3） | **未实现**，记录里 `gate_independent` 恒为 `NOT_RUN` |
| 论文作者/单位/授权声明 | 需人填 |
| 更高重复数（n>6） | 未跑；当前零结果已足以支持「未检出差异」的表述 |

### 验收

五分支合并干净，**346 passed**，协议自检 PASS，交叉检查 agree，审计 46/46 覆盖 0 UNMET，layout 演练 exit 0，两个实例 `discriminates=True`。
