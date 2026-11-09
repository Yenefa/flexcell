# W5-E2d — 显式行动指令：真实 Gazebo 多场景自改进 **2/2 成功**

协议：[`docs/W5E2D_PREREGISTRATION.md`](../../../docs/W5E2D_PREREGISTRATION.md)。
与 E2c 同场景/门/预算，仅 task.md 增加"先执行一次、不查 gate/、直接编辑 zone_2_x"。

| rep | success | iters | tokens | 写文件 | 首写前读取 | 目标门 | normal | regrasp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rep1 | ✅ | 3 | 3089 | 是 | 2 | PASS | PASS | PASS |
| rep2 | ✅ | 2 | 1999 | 是 | 2 | PASS | PASS | PASS |

## 判读（按预注册）
- 两次都写文件且**三门全 PASS** → 记"显式行动指令可改变行为（n=2）"；
- 对比 E2c：0/2 成功、阅读 31 次；E2d：2/2 成功、首写前读取显著减少；
- n=2 探索性；单任务、单模型（deepseek-chat）；缺陷人工注入；
- 不能外推为"模型已具备自主自改进"，只说明任务指令对行动缺口有直接影响。

```bash
python3 experiments/pilot-001/runs/p1.5-w5e2d-20261109/verify.py
```
