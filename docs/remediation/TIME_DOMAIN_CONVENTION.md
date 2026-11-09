# 时间域规范（P2-D）

本文件是 FlexCell 的时间域约定，代码评审以它为准。**不要求批量替换 `time.time()`**，
只要求每一处用法落在正确的域里。

## 1. 三个域

| 域 | API | 允许用途 | 禁止用途 |
| --- | --- | --- | --- |
| Wall clock | `time.time()` / `datetime.now()` | 日志展示、绝对时间戳、审计（`wall_ts`、`created_at_unix`、episode 的 start/end） | 超时、耗时、缓存年龄 |
| Monotonic | `time.monotonic()` | 超时、deadline、耗时、缓存/采样年龄、看门狗 | 跨进程比较、写入 ROS 消息头 |
| ROS clock | `node.get_clock().now()` | ROS 消息 `header.stamp`、仿真时间、轨迹时间戳 | 真实耗时测量（仿真可暂停/加速） |
| 高精度耗时 | `time.perf_counter_ns()` | 路径耗时、延迟测量（`elapsed_ms`、`decide_latency_ms`） | 跨进程持久化 |

## 2. 硬性规则

1. **超时/年龄/耗时一律 `monotonic`**，它不受系统时钟调整影响。
2. **"从未收到"不能用数值哨兵**。用 `None` 表示未知；用 `0.0` 与 `monotonic` 相减会把
   "从未到达"算成"开机至今"，在刚启动的主机上看起来**是新鲜的**——这是本轮修掉的真实缺陷。
3. **命名必须暴露域**：`_js_monotonic` 而非 `_js_wall`，`created_at_unix` 而非 `created_at`。
4. **日志时间戳要标域**：episode 的 `timestamps.clock = "wall_unix_seconds"`。
5. **不跨域比较**。ROS 仿真时间与 `monotonic` 之间没有固定偏移。

## 3. 本轮审计结果

扫描 `flexcell_skills` 全部 `time.time()` / `time.monotonic()` / `perf_counter` 用法：

| 位置 | 用法 | 判定 |
| --- | --- | --- |
| `episode.py` start/end | wall | **正确**（审计用途），补 `clock` 标签 |
| `inference_budget.py` `created_at_unix` / `voided_at_unix` | wall | **正确**（账本审计） |
| `move_to_pose_server.py` `wall_ts` | wall | **正确**（日志） |
| `move_to_pose_server.py` `_js_wall` | monotonic 存于 wall 名下 + `0.0` 哨兵 | **缺陷，已修** |
| 各 server `elapsed_ms` / deadline | monotonic | **正确** |
| `task_fsm_server.py` `duration_s` | monotonic | **正确** |
| `llm_policy.py` 延迟 | `perf_counter_ns` | **正确** |

结论：**未发现跨域比较**，只有一处哨兵缺陷与一处命名误导。未做批量替换。

## 4. 后续
- 新增计时代码遵循上表；
- `move_to_pose_server.py` 中 `get_clock()` 与 `source_ns` 的比较已在同一域内（ROS clock），保持；
- 若引入仿真时间加速，`elapsed_ms` 仍取 monotonic（真实墙钟耗时），不要改成仿真时间。
- `move_to_pose_server.py` 中 `get_clock()` 与 `source_ns` 的比较已在同一域内（ROS clock），保持。
