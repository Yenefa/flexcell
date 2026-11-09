# W5-E1 — 合成层自改进闭环试点（2026-11-09）

任务：`skill/recovery.py` 对可恢复失败（error 30）一律 ABORT；agent 需修复它，同时不破坏既有回归。
验收：`gate/acceptance.py` = 目标场景 PASS **且** 回归 0 失败（`gate/run_regression.py`），gate/ 与回归测试为 protected。

| arm | 信息 | success | iters | tokens | target | regression_rc |
| --- | --- | --- | --- | --- | --- | --- |
| w5a | failure output only | ✅ | 4 | 3521 | true | 0 |
| w5b | failure output + verdict | ❌ | 5 | 5226 | false | 0 |

## 结果
- **W5A（仅失败输出）**：4 轮，写出正确修复（`if error_code in RECOVERABLE_ERRORS and budget > 0: return "OBSERVE"`），目标 trace `OBSERVE → DONE`，**回归 rc 0**，独立验收 PASS；
- **W5B（+独立 verdict）**：5 轮结束仍未修改代码，目标失败；
- **n=1/臂**，不能说明"verdict 信息有害"；只记录现象。

## 过程中修复的 harness 缺陷（非实验证据）
1. `gate/sim.py` 未把工作区根加入 `sys.path` → 目标恒失败；
2. 技能文档未声明允许动作集 → agent 写了不存在的 `RECOVER`；
3. Windows 侧无 pytest → 回归门恒失败；改用无依赖 `gate/run_regression.py`（agent 与验收共用）。

## 意义
- **"失败 → 改代码 → 目标验收 + 回归 → 独立验证"闭环首次跑通**（W5A）；
- 回归门确实拦住过宽修复（早期尝试无条件下 OBSERVE，回归失败）；
- 尚未在真实 Gazebo 上做同类闭环（下一步 W5-E2）。
