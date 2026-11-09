# P1.6 — 24H 研究冲刺（2026-11-10）

- 报告：[`docs/24H_RESEARCH_REPORT.md`](../../../docs/24H_RESEARCH_REPORT.md)
- 矩阵：[`docs/EXPERIMENT_MATRIX.md`](../../../docs/EXPERIMENT_MATRIX.md)
- 工具缺陷根因：[`TOOLING_DEFECT.md`](TOOLING_DEFECT.md)
- Level B 归因：[`LEVELB_FAILURE_ATTRIBUTION.md`](LEVELB_FAILURE_ATTRIBUTION.md)
- 检查点：[`CHECKPOINT.json`](CHECKPOINT.json)

## 目录
- `p0-w5e2d-flash/`：Flash 复现成功（3 轮 / 3170 tokens）；
- `w5s-baseline/`：Level B 缺陷基线（dual FAIL、normal/regrasp PASS、build OK）；
- `p1-w5s-levelb-r1..r5`、`p1-w5s-levelb-v4pro/`：五次源码修复尝试（全部失败，含 transcript）。

## 说明
本轮因 API 额度（HTTP 402）中止；Level B 在工具修复后尚未重跑。
