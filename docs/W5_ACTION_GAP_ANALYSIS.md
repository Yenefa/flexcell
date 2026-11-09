# W5 行动缺口分析 — "只读不写"失败样本（2026-11-09）

> 样本：9 次真实运行（8 失败 / 1 成功），全部来自 W5 与 W6 的真实 Gazebo 任务。
> 数据从每次运行的 `events.jsonl` 逐轮调用统计得出，不是事后叙述。

## 1. 样本表
| run | success | iters | tokens | 写文件 | 首轮工具 | exec 次数 | read/list 次数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| W6-cold-c1 | ❌ | 5 | 6368 | 否 | run_checks,read_telemetry | 4 | 10 |
| W6-cold-c2 | ❌ | 5 | 5534 | 否 | run_checks,read_telemetry,read_verification | 4 | 5 |
| W6-cold-c3 | ❌ | 5 | 6344 | 否 | run_checks,read_telemetry | 4 | 9 |
| W5B | ❌ | 5 | 5226 | 否 | read_file,read_file | 0 | 16 |
| W5-E2-p2 | ❌ | 4 | 8709 | 否 | read_file,run_checks | 5 | 8 |
| W5-E2-p3 | ❌ | 4 | 7500 | 否 | list_dir,read_file | 0 | 19 |
| W5-E2b-rep1 | ✅ | 5 | 5161 | 是 | read_file,list_dir | 2 | 14 |
| W5-E2c-rep1 | ❌ | 6 | 7519 | 否 | list_dir,read_file | 2 | 31 |
| W5-E2c-rep2 | ❌ | 6 | 7582 | 否 | list_dir,read_file | 3 | 31 |

## 2. 观察（描述性，不作统计结论）
1. **失败样本全部没有写操作**：8 次失败中没有一次 `write_file`/`edit_file`；
2. 失败样本的阅读次数跨度很大（5–31），但执行次数并不少（0–5）：**不是不会跑，而是不落笔**；
3. 成功样本（E2b rep1）阅读 14 次、执行 2 次后写入；
4. **E2c 两个样本阅读 31 次**（任务文本提到三个场景），探索量最大，仍未写；
5. 合成层 W5B 也是"只读"（16 次阅读、0 次执行、0 次写），说明该模式不只出现在真实 Gazebo。

## 3. 假设（待检验，不是结论）
- **H1（探索胃口）**：任务文本提到的场景/文件越多，agent 越倾向继续读，越难进入写；
- **H2（首轮锚定）**：首轮若以 `run_execution` 开场（看到失败），更可能很快写；
- **H3（工具可用性）**：`edit_file`/`list_dir` 已补，仍失败 → 不是工具缺失。

现有 9 个样本不足以区分 H1/H2；需要预注册实验。

## 4. 下一步（W5-E2d 预注册要点）
- 任务与 E2c 相同（目标双门 + normal/regrasp 回归），**只改 task.md**：
  明确"先执行一次目标场景，不要检查 gate/ 或其他文件，然后直接编辑 config/week1.yaml"；
- 指标：是否写、首写前读取次数、迭代、token、三门 PASS；
- 判读：若写且三门 PASS → H1 得到支持（提示可改变行为）；若仍不写 → 记录为模型行为限制。
