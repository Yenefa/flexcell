# Level C′ — 无位置提示 + 先运行场景：**有效判分，结论 FAIL**

## 设计
与 Level C 相同的**无位置提示**任务文本，只增加一句"先运行一次场景看真实失败，不要浪费轮次列目录"。
目的：把 Level C 的"探索成本"与"诊断能力"分开。

## 关键：判分工具链终于有效
前三次尝试判分均为 `HARNESS_ERROR`（仿真栈未启动）。本次在 `gazebo.run_smoke` 的**判分前清理**中
加入了更彻底的一步：除了 `gz sim`，还清理 gz 的 ruby 启动器、`ros2 daemon stop`、
以及 `/dev/shm/fastrtps_*` 共享内存段（WSL 内无法 `wsl --shutdown`，只能靠这一步）。
**随后判分返回真实任务级结论**：`target=ROBOT_FAILURE`、`regression_normal=PASS`。

## 结果（有效）
| 项 | 值 |
| --- | --- |
| 模型 | `deepseek-flash` |
| 迭代 | 10 |
| Token | 51,395 |
| `run_execution` 次数 | **9** |
| 是否看到真实失败 | **是**（`ROBOT_FAILURE`） |
| 源码编辑 | **0** |
| 目标场景 | **ROBOT_FAILURE**（缺陷未修复） |
| 回归 `normal` | PASS |
| `claim_success` / `false_success` | false / false |

缺陷行 `task_fsm_server.py:1236` 保持注入状态（`zones[zone_of[self._obj_a]]`），确认未被修改。

## 判读（这是本轮最有信息量的负结果）
1. **不是"没看到证据"**：agent 运行了 9 次场景，每次都拿到 `ROBOT_FAILURE`；
2. **也不是"探索不足"**：第 1 轮就执行了场景（指令生效）；
3. **卡在"证据 → 定位"的转换**：它在 `list_dir` / `read_file` 之间反复切换，
   始终没有把"第二个对象放错位置"缩小到那一行赋值的范围；
4. 对比 Level B（点名文件）：**2/2 成功、5–6 轮**。差别不在模型能力，而在**定位成本**。

## 边界
- n=1 有效样本（另有 3 次因判分无效作废），**探索性，不外推**；
- 与 Level B **严格分开统计**，不合并；
- 迭代预算 24 轮，实际用 10 轮即停止（模型自行结束）。

## 复现
```bash
bash ci-public-window/scripts/run_levelc2.sh /tmp/levelc2 W5A
python3 setup/acceptance/w5_levelcprime_20261110/verify.py
```
