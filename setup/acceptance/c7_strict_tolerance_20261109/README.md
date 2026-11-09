# C7 — 严格验证（2 cm 容差）下 FSM vs MTC，3+3（2026-11-09）

协议：[`docs/C7_PREREGISTRATION.md`](../../../docs/C7_PREREGISTRATION.md)（运行前冻结）。
配置覆盖：`task_fsm_server.demo_verify_tolerance_m = 0.02`（默认 0.06），经 `--config-override`。

| run | arm | status | wall (s) | fingerprint 前缀 |
| --- | --- | --- | --- | --- |
| legacy-a | fsm | PASS | 13.965 | 2a08bfc7 |
| mtc-b | mtc | PASS | 15.923 | d9f2ddf6 |
| mtc-c | mtc | PASS | 15.87 | d9f2ddf6 |
| legacy-d | fsm | PASS | 14.02 | 2a08bfc7 |
| legacy-e | fsm | PASS | 14.319 | 2a08bfc7 |
| mtc-f | mtc | PASS | 17.526 | d9f2ddf6 |

| 指标 | FSM | MTC |
| --- | --- | --- |
| 成功 | **3/3** | **3/3** |
| 平均 wall | **14.101 s** | **16.440 s（+2.338 s ≈ +16.6%）** |

## 判读（按协议）
- 收紧到 2 cm 后两臂仍 3/3 → 记"**2 cm 容差未区分两臂**"，不宣称等价；
- MTC 仍更慢（+16.6%），方向与 C3/C6 一致；n=3，探索性；
- fingerprint 相对默认容差发生变化（`2a08bfc7…` / `d9f2ddf6…`），确认覆盖生效；
- 未修改容差/验收器使某臂通过。

```bash
python3 setup/acceptance/c7_strict_tolerance_20261109/verify.py
```
