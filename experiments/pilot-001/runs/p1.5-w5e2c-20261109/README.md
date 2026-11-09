# W5-E2c — 多场景回归门（normal + regrasp），2 次试点均**失败**

协议：[`docs/W5E2C_PREREGISTRATION.md`](../../../docs/W5E2C_PREREGISTRATION.md)。

| rep | success | iters | tokens | 是否写文件 | 目标门 | normal | regrasp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rep1 | ❌ | 6 | 7519 | 否 | ROBOT_FAILURE | PASS | PASS |
| rep2 | ❌ | 6 | 7582 | 否 | ROBOT_FAILURE | PASS | PASS |

## 判读
- 两次都**未写文件**（探索耗尽 6 轮预算），与 W5-E2 的"只读不写"模式一致；
- 回归门本身正常：normal 与 regrasp 在未修复配置下仍 PASS（说明它们不受 `zone_2` 影响）；
- **多场景回归门未验证成功**；W5-E2b（单回归门）的 3/3 仍是唯一真实层证据；
- 按资源规则停止调参（0/2），不再增加预算或改写任务文本。

## 限制
- n=2 均失败；不能说明多场景回归不可行，只能说当前任务/预算下 agent 未行动；
- 后续若再做，需要新的协议（如明确"先写后验"步骤或不同模型），并重新预注册。
