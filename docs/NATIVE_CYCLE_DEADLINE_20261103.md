# Native 五循环 worker 预算修复与本机证据 · 2026-11-03

CI `native-five-cycle-smoke`（run 41407787100）在 `scripts/native_cycle_window.py`
的固定 `timeout=330` 处被杀。该轮**五轮协议动作全部完成**（`native-events.jsonl`
记录到第 5 轮 `final_status`，`transport_ok=true`），被杀的是每轮之后的原始证据审计。
本文件记录原因读数、修复边界与本机验证；**CI 尚未重跑**。

## 已确认的读数（原 ZIP 未改一字）

- 每轮协议墙钟 38.8–41.6 s（合计 196 s），preflight RTF 0.358。
- 审计间隔（上一轮 `final_status` 回复 → 下一轮首个请求）：14.4 / 21.2 / 28.3 / 35.5 s，
  第 5 轮审计在 330 s 被杀时仍未完成；总需求约 341 s。
- CI 端每行审计成本约 3.1 ms（第 3 轮 9,042 行 / 28.3 s），本机同一数据约 0.25 ms/行，
  差约 12 倍（2 核 runner + 仿真/录制并发）。

## 两个缺陷

1. **审计读到当时 EOF，把本轮审计运行期间仿真继续追加的行也算了进来。**
   审计 i 的输入 = 本轮行 + 审计 i-1 运行期间新写入的行，于是审计 i 更慢、
   审计 i+1 输入更大，形成反馈（CI 间隔逐轮 +7 s）。
2. **330 s 是固定值，低于声明自身允许的下限。** 五轮 ×（1.05 s 预置 + 10.1 s 保持 +
   1.0 s 落定）= 60.75 sim s；声明允许 `min_preflight_rtf=0.3`，纯物理下限
   **202.5 s**，再加任何门禁都装不进 330 s。

## 修复

- `audit_cycle()` 的读取以本轮最后声明帧 `retired_probe_sim_ns` 为界，并以上下文打开时的
  文件长度为界；越界行不读、不丢，留给下一轮。原始字节不变；`verify_run` 仍在退出时整文件复核，
  `verify_cycle` 仍要求本轮 `reference−1 s … release+0.5 s` 的 2 ms 连续步。
- 期限由声明推导，不再固定：
  `floor = max_cycles × (1.05 s + hold + settle) / min_preflight_rtf`，
  加 `5 × 25 s` 审计配额与 `30 s` 客户端配额 → 本声明为 **358 s**。
  每轮 receipt 记录 `audit`（行数、边界、解析/观测/校验耗时）；`worker.json` 与
  `result.json` 记录 `worker_deadline_s`；`verify_run` 拒绝低于声明下限的 receipt
  （旧 receipt 无此字段时按原行为放行，历史证据不受影响）。
- 新声明 `infra/native-five-cycle-window-after-audit-boundary.json`
  （SHA `b4cbee7831e4999b12dca46f64b70699a93fe74984ee041bf5d3293e46209148`），
  CI 任务改指向它；物理/时间门限与上一份声明逐字相同，只增加审计与期限政策。
- 未改动：10 s 附着、2 mm/1° 跟随、500 ms 新鲜度、2 ms 连续、20 ms 绑定、
  所有权拒绝、no replacements、`default_admission=NO_GO`。

## 本机验证

环境：WSL2 Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic / 合并安装 + Release /
`rmw_cyclonedds_cpp` / `ROS_DOMAIN_ID=45`；固定臂 native 窗口（`robot_motion_tasks=0`）。

| 运行 | 声明 | 结论 | RTF | 每轮审计耗时（s） | 切片行数 |
| --- | --- | --- | --- | --- | --- |
| 修复前（只加计时） | after-audit-lifetime | `FIVE_NATIVE_CYCLES_PASS` | 0.754 | 5.17 / 2.46 / 1.73 / 1.74 / 1.94 | 17,525 / 7,867 / 6,930 / 6,775 / 6,783 |
| 修复后（开发版） | after-audit-lifetime | `FIVE_NATIVE_CYCLES_PASS` | 0.898 | 8.56 / 2.78 / 3.16 / 2.23 / 2.01 | 17,863 / 8,252 / 6,947 / 6,797 / 6,828 |
| **修复后（声明窗口）** | **after-audit-boundary** | **`FIVE_NATIVE_CYCLES_PASS`** | **0.992** | **4.13 / 2.06 / 1.67 / 1.75 / 1.94** | **19,537 / 7,931 / 6,858 / 6,776 / 6,756** |

声明窗口一次运行：`worker_exit=0`、`recorder_exit=0`、`owned_exit=0`，
`worker_deadline_s=358`，第 5 轮审计完成，事后复位与 19 项健康检查通过。
证据目录 `setup/acceptance/native_cycle_budget_20261103/`（`result.json`、`worker.json`、
`identity.json`、原始日志 SHA256；100 MB 级 2 ms 原始日志留在本机，不入仓）。

单测：包内 843 项通过、0 失败（`test_native_cycle_window.py` 含 5 项新增：
边界不越读、审计不改原始文件并记录耗时、期限不低于声明下限、receipt 低于下限被拒、
旧 receipt 无该字段仍按原行为；40 文件静态扫描与两个历史 native 回放器仍退出 0）。

## 未完成与边界

- **CI 未重跑**：本机 RTF 0.99–0.75，不代表 2 核 runner 的 0.36。本文件**不声明 CI 已修复**；
  358 s 的余量（预计修复后 CI 约 196 s 协议 + 5 × 10–20 s 审计）需要一次真实 CI 运行确认。
- 本机三次窗口是同一台机器、各一次，不是统计基线；不构成成功率或延迟保证。
- 审计仍是串行 CPU 工作；没有并行化、没有改物理门限、没有改 D3 准入与 n≥50 冻结。
