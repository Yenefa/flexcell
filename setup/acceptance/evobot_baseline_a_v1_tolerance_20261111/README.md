# Baseline A-v1 容差实验：0.02 vs 0.06

**状态：** 实验设计完成，等待 A-v0 批次收口后执行
**日期：** 2026-11-11
**裁决来源：** 用户第 3 轮裁决

## 要回答的问题

A-v0 在 T05（relay）上 0/2，其中至少一个是**阶段级假失败**：

    native 组件:  terminal_status=SUCCEEDED, error_code=0, error=0.0497 m,
                  detail="task done: all assignments verified"
    composite:    error_code=62 "native terminal/verification unconfirmed"
    独立验收器:   0.0497 m < 0.06 m 区域半径 -> 本应通过

position_tolerance_m 在 contracts/composite.py 里被读一次、用**四**次：

| 行 | 用途 |
| --- | --- |
| 196 | 每阶段执行**前**的链状态漂移检查（matches） |
| 206 | native_success()：native 放置是否被接受 |
| 210 | 每阶段执行**后**的实测位置检查 |
| 217 | 整条链最终状态检查 |

而 matches() 对**链中每个物体**施加该容差：

    def matches(actual, expected, tolerance):
        return all(math.dist(actual[name], xyz) <= tolerance for name, xyz in expected.items())

**所以 0.02 → 0.06 不是「放宽放置判定」，而是同时放宽了漂移保护。一个参数，两种语义。**

独立验收器的 0.06 只是**水平半径**，它另外要求静态高度误差 ≤ 0.02、未移动物体偏移 ≤ 0.015，
并验证中转路径。两者不是同一个量，不能互相替代。

## 实验设计

| 项 | 裁决 |
| --- | --- |
| 运行中的 72 实例 A-v0 | **继续执行，绝不修改** |
| A-v0 原始结果 | **永久冻结** |
| 0.02 → 0.06 | 仅作为 **A-v1 的独立实验变量** |
| native_success() | **暂不修改** |
| 全局漂移阈值 | **不默认放宽** |
| 独立验收器 | **不修改** |
| A-v1 正式采用 | 必须通过配对实验 + 安全回归 |

**受控对照：** 两个臂使用完全相同的流水线（世界生成、起栈、派发、抓真值、独立评分），
**只有计划构建器的 tolerance 与输出目录不同**。计划构建器是独立文件
ci-public-window/scripts/evobot_build_plan_tol.py，它 **import** 冻结的
build_composite_plan.py 而不修改它——A-v0 的 definition_sha256 保持不变。

## 必须记录的量（每臂）

1. 每阶段：terminal_status、final_position_error_m、object_at_place、是否被 COMMITTED
2. composite 终态：outcome、error_code、detail
3. 独立验收器：passed、failed_clauses
4. 最终观测：每个物体的实测位置

## 副作用检查（比通过率更重要）

- 任务要求**保持不动**的物体是否发生了超出允许的漂移？
- 中转阶段是否在物体**没有真正到达中转区**的情况下被 COMMITTED？
- 放宽后的容差是否让漂移保护**睡过去了**（某阶段移动了不该移动的物体却没被发现）？

## 判定规则

| 结果 | 处置 |
| --- | --- |
| 0.06 有效且无副作用 | 发布明确标记的 A-v1，与 A-v0 **并列**统计 |
| 0.06 引入不安全/不正确的阶段判定 | **修改 A-v1 的 Composite 契约**，把「目标区域验收」与「状态漂移保护」**分离**，不靠一个参数承担两种语义 |
| 两者皆失败 | 记录失败机制，A-v0 保持为唯一基线 |

## 后续

A-v1 确认后，Baseline B/C 必须在**同一执行契约**下重新对照——否则 Agent 会因使用不同容差
而获得虚假的性能优势。

## 不做什么

- 不为提高通过率而修改独立验收器
- 不把「composite 接受」当作「任务成功」；两者分别统计
- 不在 A-v0 批次运行期间修改任何冻结组件
