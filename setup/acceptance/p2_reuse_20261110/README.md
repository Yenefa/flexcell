# P2 经验复用实验（run1）— **FAIL，且被预算截断**

预注册：`docs/P2_PREREGISTRATION.md`。

## 设计（换缺陷，避免测记忆）
| 项 | 值 |
| --- | --- |
| 缺陷位置 | **VERIFY 分支**（1320 行），非 Level C′ 的 PLACE 分支 |
| `suspect_regions` | **关闭**（回到 C14 的纯证据水平） |
| 经验笔记 | 提供（`experience/experience_place_target.json`，逐字复制已归档记录） |
| 任务文本 | 无文件名、无行号、无修复方向 |

## 结果
| 项 | 值 |
| --- | --- |
| 迭代 / Token | 7 / **54,142（超预算 35%）** |
| `budget_exceeded` | **是**（`runner.py:107`，上限 40k） |
| `run_execution` | **0 次** |
| `list_dir` / `read_file` | 17 / 12 |
| `edit_file` | **0** |
| 是否读到经验笔记 | **是**（工具参数中出现 `experience`） |
| 目标场景 | ROBOT_FAILURE（未修复） |
| 回归 `normal` / `regrasp` | PASS / PASS |

## 判读（按预注册判据：0 次编辑 → **H0**）

**经验笔记没有降低定位成本**：agent 确实读了笔记，但仍在目录遍历上耗尽预算，
连场景都没运行（`run_execution` 0 次）。

按 24H 目标 §4 的三条区分，**第 ③ 项（agent 真正复用经验）未获证据**，
因此**不宣称**已开始实现 Experience-Driven Improvement。

## 必须记录的限制
- 本次是**被预算截断**的，不能推断"给更多预算也无效"；
- n=1；
- 笔记是**工程师归纳**的（第 ② 项也未达成），所以这里测的是"现成经验文件是否有用"，
  比目标要求的"agent 自主归纳再复用"更弱。
