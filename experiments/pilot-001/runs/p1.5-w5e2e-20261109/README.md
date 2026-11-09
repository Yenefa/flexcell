# W5-E2e — 第二种故障类型（对象未注册）**2/2 成功**

协议：[`docs/W5E2E_PREREGISTRATION.md`](../../../docs/W5E2E_PREREGISTRATION.md)。
缺陷：`observe_server.tracked_objects` 缺 `target_box_b`（探测确认 `ERR_SAFETY_REJECTED: target_not_available`）。

| rep | success | iters | tokens | 目标门 | normal | regrasp | 配置含 B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rep1 | ✅ | 4 | 4063 | PASS | PASS | PASS | 是 |
| rep2 | ✅ | 4 | 4060 | PASS | PASS | PASS | 是 |

## 判读
- 2/2 成功，三门全 PASS；与 E2d（可达性缺陷）**机制不同**（注册缺失 vs 目标不可达）；
- 同一显式行动指令在两种缺陷上都有效；n=2、单模型（deepseek-chat）；
- 探测（`probe.json`）只是可行性验证，不进入统计。
