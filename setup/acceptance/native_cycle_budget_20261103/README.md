# Native 五循环预算修复证据 · 2026-11-03

声明窗口 `infra/native-five-cycle-window-after-audit-boundary.json`
（SHA `b4cbee7831e4999b12dca46f64b70699a93fe74984ee041bf5d3293e46209148`）在本机的一次运行。

- `result.json`：`status=PASS`、`worker_deadline_s=358`、`preflight_rtf=0.992`、
  `worker_exit=0`、`recorder_exit=0`、`owned_exit=0`，`evidence.status=FIVE_NATIVE_CYCLES_PASS`。
- `worker.json`：五轮 receipt，每轮带 `audit`（边界帧、行数、解析/观测/校验耗时）。
- `identity.json`：源码/安装/原生库指纹（`scripts/` 与 `infra/` 的 SHA 亦在内）。
- `raw-manifest.sha256`：三份 2 ms 原始日志的 SHA256 与字节数。
  100 MB 级原始日志本身留在本机（`/tmp/native5-final/`），不入仓；重跑同一声明可再生成。

本次运行只证明：修复后的审计切片按声明边界收敛、五轮窗口仍完整 PASS。
它**不**证明 CI 已修复（本机 RTF 0.99，CI runner 为 0.36），也不构成统计基线。
见 [读数与边界](../../../docs/NATIVE_CYCLE_DEADLINE_20261103.md)。
