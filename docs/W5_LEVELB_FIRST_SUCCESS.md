# W5 Level B — 首次真实源码级自主修复（2026-11-10）

> **结论：达成。** Agent 从真实执行失败证据出发，定位并修改真实技能源码，
> 构建后目标场景 PASS，两项回归 PASS，冻结验收器未改动。

## 1. 结果

| 项 | 值 |
| --- | --- |
| 模型 | `deepseek-flash`（请求=返回，指纹 `2caaf9b9`） |
| 迭代 | **5** |
| Token | **23,754** |
| agent 耗时 | 80.1 s |
| 执行耗时 | 73.5 s |
| 目标场景 `dual_object` | **PASS** |
| 回归 `normal` | **PASS** |
| 回归 `regrasp` | **PASS** |
| 构建 | returncode 0 |
| `claim_success` | **false**（未自我宣称成功） |
| `false_success` | **false** |
| 验收器 `gate/acceptance.py` | **未修改**（1488 B 原始文件） |

## 2. Agent 的真实行动序列（来自 `events.jsonl`）

| 迭代 | 动作 |
| --- | --- |
| 1–3 | `run_checks` + `read_file` 分页阅读 `task_fsm_server.py` |
| 4 | **`run_execution`** → 得到真实失败：`ROBOT_FAILURE` / `ERR_RECOVERY_EXHAUSTED` |
| 5 | **`edit_file`**：`zones[zone_of[self._obj_a]]` → `zones[zone_of[decision.target]]` |

第 5 轮的编辑正是注入缺陷的**精确逆操作**，且发生在**看到真实失败证据之后**
（`first_run < first_edit`，由 `verify.py` 断言）。

## 3. 注入的缺陷

`w5s.DEFECT_FROM`（正确）→ `DEFECT_TO`（注入）：
```
正确: zx, zy, zz = zones[zone_of[decision.target]]
注入: zx, zy, zz = zones[zone_of[self._obj_a]]
```
含缺陷时 A 腿与 B 腿都被放到 `object_a` 的 zone，B 的验证偏差约 0.3 m。

## 4. 为什么这次成功而之前"只读不写"（关键披露）

前 6 次尝试全部失败。**失败原因是验证工具链自身的 4 个真实缺陷**，不是模型能力：

| # | 缺陷 | 后果 | 修复 |
| --- | --- | --- | --- |
| 1 | `search_code` 传**文件路径**时用 `rglob` 于文件 | 恒返回 `(no matches)`，agent 无法定位 | 单文件搜索分支 |
| 2 | `gazebo.export/_to_wsl` 无条件 `split(":")[1]` | 每次 `run_execution` 抛 `IndexError`，**agent 从未拿到失败证据** | 统一 `_to_wsl_path` |
| 3 | `subprocess.run(["wsl", ...])` 在 WSL 内无 `wsl` 命令 | `run_execution` 抛 `FileNotFoundError` | `_bash()` 双模式 |
| 4 | `run_execution` 结果未在提示中体现执行次数 | agent 反复阅读而不运行 | 提示加入 "Executions run so far: N" |

另外 `T-W5S` 的 `max_iterations` 由 10 提到 24（1436 行文件需要更多页）。

**披露**：这 4 个修复由上层的我（工程师）完成，**不是 agent 自己修的**。
Agent 的成功发生在修复后的工具链上。这符合"修复工具层根因"的既定方向，
但必须明确：**能力提升来自工具可用性，而非模型变强**。

## 5. 复现

```bash
bash ci-public-window/scripts/run_levelb.sh /tmp/levelb W5A
bash ci-public-window/scripts/archive_levelb.sh   # 归档到 setup/acceptance/w5_levelb_20261110
python3 setup/acceptance/w5_levelb_20261110/verify.py   # -> W5_LEVELB_REAL_SOURCE_REPAIR
```

需要 `~/.config/flexcell/deepseek_api_key`；WSL 内运行，domain/partition 由 `run_levelb.sh` 隔离。

## 6. 边界（不可外推）
- **n = 1**，单次成功，不构成统计证据；
- 任务是**预注册的单一缺陷类型**（阶段转换/目标对象选择错误），不代表任意缺陷；
- Level C（减少提示泄露）**尚未运行**，本结果**不得**与 Level C 合并统计；
- 成功依赖 24 轮预算；更小预算下的成功率未知；
- 成本：23,754 tokens ≈ 0.05–0.19 RMB（按峰值未缓存价上界估算）。
