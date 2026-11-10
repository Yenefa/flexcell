# 版本基线核对（先于任何修改）

> 本文件只记录**实测的 Git 事实**，不推论、不修补。所有命令与输出可复现。

## 1. 三方关系（实测）

| 对象 | 值 | 说明 |
| --- | --- | --- |
| 远程 `origin/main` | `ebe27f0788…` | 与 GitHub 连接器读到的一致 |
| 本地整改分支 `autonomous/flexcell-remediation`（`wt-comp`） | `bd7e7fc` | **基于 `ebe27f0`**，领先 27 个提交 |
| `wt-comp` 与 `origin/main` 的 merge-base | `ebe27f0` | ✅ `origin/main` 是 HEAD 的祖先 |
| EGM 审查用的工作树 `code-clone` | `db142fd` | 分支 `fix/legacy-attached-point` **尖端** |
| `db142fd` 相对 `origin/main` | 落后 **280**，领先 **6** | ❌ **不是** main 的祖先，是**未合并分支** |

**结论**：`db142fd` 是 `fix/legacy-attached-point` 的历史尖端，不是主线。
EGM 报告里"审查基准 `db142fd`"描述的是**被审工作树的 HEAD**，不是 `origin/main`。

## 2. 因此产生的一个真实偏差（必须记录）

仓库内的 `docs/ARCHITECTURE.md` 自称基准 `a9b6a62`（2026-10-08），
而 `a9b6a62` 落后 `origin/main` **405 个提交**。
文档在 `db142fd` 与 `origin/main` 之间也**不同**：main 多出 7 行（`Competition packaging (IYAIC 2026)` 段）。

→ **任何基于 `db142fd` 的架构结论都必须回到 `origin/main` 复核**，否则等于审旧稿。

## 3. 在 `origin/main` 上的复核结果

| EGM 关键结论 | `origin/main` 上是否仍成立 | 证据 |
| --- | --- | --- |
| MTC 在文档中写"not implemented" | **仍成立** | `docs/ARCHITECTURE.md:103-105` 原文；而 main 上存在 `mtc_motion.py`、`mtc_planner.cpp`、`test_mtc_motion.py` |
| 文档基准提交陈旧 | **仍成立，且更严重** | 自称 `a9b6a62`，落后 main **405** 提交 |
| `19-check strict gate` 魔法数字 | **仍成立** | `docs/ARCHITECTURE.md:84` |
| E-020/E-021 被当现行证据 | **仍成立** | 文档开头即引用 E-020/E-021 |
| carry 后端枚举含不存在标识符 | 需在 main 上逐条比对（未在本轮展开） | — |

## 4. `_egm-review/` 为什么不在远程

实测：`_egm-review/` 位于 **workspace 根目录**（`C:\Users\fuker\Desktop\workspace\_egm-review`），
**不在 flexcell 仓库内**，全历史 `git log --all -- _egm-review/*` 为空。

所以"远程 main 找不到 `EGM_REVIEW_REPORT.md`"是**预期行为**，不是丢失：它从未被提交进仓库。

## 5. 修改前的准入条件（已满足）

1. ✅ `origin/main` 是当前工作分支的祖先（不会覆盖更新成果）；
2. ✅ 本地 27 个提交均在 `ebe27f0` 之上，未触碰他人分支；
3. ✅ 未对 `code-clone` 做任何写操作；
4. ✅ 本轮新增内容**只涉及文档与台账生成脚本**，不修改 FlexCell 架构、不触碰 Gazebo / ROS 2 执行代码。

## 6. 仍需人工决定

- `fix/legacy-attached-point`（含 `db142fd` 在内的 6 个提交）**是否应合入 main** —— 这是分支归属问题，需仓库所有者决定；
- 修复 `ARCHITECTURE.md` 的陈旧基准与 MTC 陈述，应在 **`origin/main`** 上另开分支进行，不在本整改分支里顺手改。
