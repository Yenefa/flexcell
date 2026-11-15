# 研究入口与运行模块分离

这些工具准备研究输入、调用模型、分析已有实验记录；它们不是机械臂执行技能。
可复用规划和有界恢复留在 `runtime/`，模型与实验依赖由外层驱动提供。

| 原入口 | 当前入口 |
|---|---|
| `runtime/planner/agent_planner.py` 的 CLI | `experiments/baselines/plan_v1.py`；纯规划 API 留在原模块 |
| `runtime/planner/prepare_baseline_b.py`、`prepare_baseline_c.py` | `experiments/baselines/` 下同名文件 |
| `runtime/planner/run_baseline_b.py`、`run_baseline_a_prime.py` | `experiments/baselines/` 下同名文件 |
| `runtime/planner/verify_baseline_b.py` | `experiments/baselines/verify_baseline_b.py` |
| `runtime/verifier/self_assess.py`、`fill_self_assess.py` | `experiments/baselines/assessment/` 下同名文件 |
| `runtime/verifier/reassess_v2.py`、`reassess_v3.py`、`reassess_v4.py` | `experiments/baselines/assessment/` 下同名文件 |
| `runtime/verifier/aggregate_claims.py` | `experiments/baselines/assessment/aggregate_claims.py` |

可机读迁移清单为 [research_entrypoints.json](../../config/research_entrypoints.json)。
旧命令在其 source/evidence checkpoint 复现；原始日志、旧快照和归档中的路径不批量替换。

不调用模型的入口检查，可从任意当前目录用绝对路径运行：

```bash
python3 experiments/baselines/run_baseline_b.py \
  benchmark/tasks/train/T01-train-seed1000.json --out /tmp/baseline-dry --dry
python3 experiments/baselines/verify_baseline_b.py
```

`run_baseline_b.py` 继续使用原预算门控客户端；准备器和补评器保留旧研究客户端与
批次假设，不是新的生产入口。它们的 live 模型调用仍按原预算/授权规则执行。
本轮只验证 dry、mock 与离线反例，没有调用付费模型。

v1 CLI 还修正了既有的返回值解包错误：规划函数返回四项，旧 CLI 只解包三项；
现在显式保留 `usage`。真实模型被替身替代的检查覆盖该路径，规划函数本身未改。

同区域落点分散与失败分类的旧开发导入路径仍可用，且导出的是 Runtime 纯模块中的
同一函数对象。经验路由已指向新的实际实现位置，研发逻辑不会成为执行模块的依赖。
