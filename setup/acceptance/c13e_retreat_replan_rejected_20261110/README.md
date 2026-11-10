# C13e — 拆分撤回规划：**尝试一次，失败，已回退**

## 1. 预注册
`docs/C13E_PREREGISTRATION.md`（写于改代码之前）：
**H1**：把 `[hover, descend, retreat]` 拆成先 `[hover, descend]`、
执行完再单独规划 `[retreat]`，撤回起点就来自实测状态，MTC 应能完成。

## 2. 实际结果：**H0 + 回归**

| 臂 | 修改前 | 修改后 |
| --- | --- | --- |
| `mtc-constrained` | `PLACE_B` 失败 | **`PLACE_A` 失败**（更早） |
| `mtc-default` | **PASS 6/6** | **`PLACE_A` 失败（回归！）** |
| `legacy-constrained` | PASS 6/6 | PASS 6/6 |

## 3. 失败原因（明确、可查）
```
MTC planning failed before execution:
  invalid operation, object, profile or stage count
```

planner 的请求校验要求 PLACE **固定 3 个阶段**（`hover, descend, retreat`）。
我只传 2 个，被直接拒绝。**这是接口契约，不是可以随便改的参数。**

## 4. 处置：按预注册第 6 条**立即回退**

```bash
git checkout -- src/flexcell/flexcell_skills/flexcell_skills/place_server.py
```

- 工作区已回到修改前（`git status` 只剩本预注册文档）；
- 已重新 `colcon build`，安装栈与仓库一致；
- **没有留下半成品代码**。

## 5. 这次失败的价值

1. **确认了 planner 的阶段数契约是硬的**——`[hover, descend, retreat]` 必须是 3 个，
   不能拆成 2+1；
2. 因此 C13d 建议的"方案 (a) 每阶段从实测重规划"**不能**用这种方式实现，
   需要改 planner 契约本身（更大改动，应独立预注册）；
3. 我按预注册回退了，**没有把失败的改动留在代码里**。

## 6. 对 C13d 结论的影响

**C13d 的根因判断不变**：撤回起点来自预测终点，实测偏差 0.0529 > 0.03。
变的是**修法可行性**：最简单的拆批方案被接口契约挡住。

剩下的可行方向：
- 改 planner 允许可变阶段数（需改 C++ 契约 + 预注册）；
- 或让轨迹携带"预期起点"，后续阶段与该预期比对（方案 b）；
- 或在 `place_server` 与 planner 之间加一次**重同步**（方案 c）。
