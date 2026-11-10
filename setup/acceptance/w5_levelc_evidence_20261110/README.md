# W5 Level C 达成 —— 无位置提示 + 失败证据自带定位

## 背景
Level C′（无提示）与 C14（无提示 + 工具清单）**均失败**：agent 运行场景 8–9 次却 **0 次编辑**，
`list_dir` 分别用了 12 / 28 次。C14 的结论是：瓶颈在**信息获取策略**——它从不"先缩小范围再精读"。

## 本轮改动（预注册见 `docs/C15_PREREGISTRATION.md`）
`W5SourceExecution.run_execution()` 的返回值改为**失败证据自带定位**：
- `suspect_regions`：从**失败本身**（失败阶段/对象）推导出的**相关代码区域**（`文件:行号: 代码`）；
- **不**说明哪一行是错的，**不**给出正确写法，**不**指出修改方向；
- 任务文本与 Level C′ **逐字相同**（仍无位置提示）。

## 结果

| | run A（证据被截断） | **run B（regions 可见）** |
| --- | --- | --- |
| 迭代 | 5 | **4** |
| Token | 25,380 | **16,937** |
| `suspect_regions` 是否送达 | **否**（被 `tail` 截断） | **是** |
| `list_dir` | 5 | **0** |
| `read_file` | 6 | 3 |
| `run_execution` | 5 | 4 |
| `edit_file` | 1 | 1 |
| 目标 `dual_object` | PASS | **PASS** |
| 回归 `normal` / `regrasp` | PASS / PASS | **PASS / PASS** |
| `claim_success` / `false_success` | false / false | **false / false** |

编辑内容（两次一致，且正确）：
```diff
-                    zx, zy, zz = zones[zone_of[self._obj_a]]
+                    zx, zy, zz = zones[zone_of[decision.target]]
```

## 归因
- **run B**：regions 送达 → `list_dir` 由 28（C14）降到 **0**，4 轮完成修复；
- **run A**：regions 被截断未送达，但 `tail` 由 900 → 2400 字符，**完整失败 trace 可见**，
  也在 5 轮内成功。说明**更完整的失败证据**本身也有价值；两次的差异无法单独归因到 regions。
- 诚实边界：run A 的**原始产物已丢失**（WSL 在两次运行间重启，`/tmp` 被清空），仅保留核验摘要，
  因此 **run A 不作为独立证据**，只有 run B 已完整归档。

## 这关闭了什么
- **Level C（less-guided diagnosis）首次达成**：无文件名、无行号、无修复方向；
- 与 Level B（点名文件）**分开记录**：这是"定位信息以证据形式提供"，不是"提示替代搜索"。

## 仍未回答
- n=1 归档（run B），需重复；
- 该机制在**其他缺陷类型**上是否同样有效，未验证。
