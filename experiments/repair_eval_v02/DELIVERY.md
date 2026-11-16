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
