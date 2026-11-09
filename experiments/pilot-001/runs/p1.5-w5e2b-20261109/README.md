# W5-E2b — 真实 Gazebo 自改进 **3/3 成功**

协议：[`docs/W5E2B_PREREGISTRATION.md`](../../../docs/W5E2B_PREREGISTRATION.md)。
缺陷：`config/week1.yaml`（最小覆盖）中 `zone_2_x=0.45`（不可达）。

| rep | success | iters | tokens | 目标门 | 回归门 |
| --- | --- | --- | --- | --- | --- |
| rep1 | ✅ | 5 | 5161 | PASS | PASS |
| rep2 | ✅ | 3 | 2668 | PASS | PASS |
| rep3 | ✅ | 3 | 2668 | PASS | PASS |

**3/3** 均由 `gate/acceptance.py` 独立跑真实 Gazebo 判定：目标场景 + 既有 normal 回归双门 PASS；
`gate/` 全程未修改（hash 守卫）。

## 闭环
`执行失败 → 读证据 → 定位不可达 → edit_file 改配置 → 目标门 PASS → 回归门 PASS → 独立验证`。

## 限制
- n=3，探索性；单任务、单模型（deepseek-chat）；缺陷为人工注入；
- W5-E2（≤3 轮）3 次失败并判 BLOCKED，E2b 是重新预注册，两者不可混算；
- M3-R（真机）未达。

```bash
python3 experiments/pilot-001/runs/p1.5-w5e2b-20261109/verify.py
```
