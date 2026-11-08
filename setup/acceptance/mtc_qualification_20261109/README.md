# MTC treatment-arm qualification — 2026-11-09（n=3）

ADR-003 的 treatment arm（MTC orchestration，同一 skill seam 之下）在**当前 main** 上的 3 次真实 Gazebo 运行。

```bash
python3 setup/acceptance/mtc_qualification_20261109/verify.py
```

| run | status | outcome | fingerprint |
| --- | --- | --- | --- |
| `result.json` | PASS | OUTCOME_SUCCEEDED | `33b420d1…` |
| `r2/result.json` | PASS | OUTCOME_SUCCEEDED | `33b420d1…` |
| `r3/result.json` | PASS | OUTCOME_SUCCEEDED | `33b420d1…` |

## 意义与边界
- 历史上（2026-10-30）MTC 首轮两次均被拒（`mtc_first_attempt_20261030`、`mtc_main_failure_20261030`）；
- 本次 **3/3 通过**，MTC 资格门重新打开；
- 但**尚未**与 FSM 在同条件下对照（C3），**不得**宣称 MTC 更优；
- 三次同一 fingerprint 说明运行条件一致。
