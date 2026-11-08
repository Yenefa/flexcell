# MTC treatment-arm qualification — 2026-11-09

ADR-003 的 treatment arm（MTC orchestration，同一 skill seam 之下）在**当前 main** 上的一次真实 Gazebo 运行。

```bash
python3 setup/acceptance/mtc_qualification_20261109/verify.py
```

## 结果
| 项 | 值 |
| --- | --- |
| status | **PASS** |
| skill_backend | `mtc`（`backend=velocity_servo`） |
| task | `OUTCOME_SUCCEEDED / ERR_NONE` |
| trace | `PICK_A(attempt=1):OK → PLACE_A:OK → VERIFY_A(attempt=1):OK` |
| runtime_fingerprint | `33b420d1…1ce116f52` |
| evidence_id | `pick_place_v1-8cff3db5` |

## 意义与边界
- 历史上（2026-10-30）MTC 首轮两次均被拒（`mtc_first_attempt_20261030`、`mtc_main_failure_20261030`）；
- 本次是**一次**通过，**不等于**对照实验完成；n=1，且未与 FSM 在同条件下做统计比较；
- 不能据此宣称 MTC 更优；只证明"资格门可以被重新打开"。
