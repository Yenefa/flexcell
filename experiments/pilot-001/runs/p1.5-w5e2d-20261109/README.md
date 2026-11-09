# W5-E2d — 显式行动指令：多场景自改进 **6/6 成功（三个模型）**

| rep | model | success | iters | tokens | 目标门 | normal | regrasp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rep1 | deepseek-chat | ✅ | 3 | 3089 | PASS | PASS | PASS |
| rep2 | deepseek-chat | ✅ | 2 | 1999 | PASS | PASS | PASS |
| rep3 | deepseek-chat | ✅ | 2 | 1983 | PASS | PASS | PASS |
| rep4 | deepseek-chat | ✅ | 3 | 3069 | PASS | PASS | PASS |
| rep5-v4pro | deepseek-v4-pro | ✅ | 3 | 3511 | PASS | PASS | PASS |
| rep6-flash | deepseek-flash | ✅ | 3 | 3132 | PASS | PASS | PASS |

## 判读
- 6/6 成功、三门全 PASS；模型：chat 4/4、**flash 1/1（当前主力 v4.1 Flash 1017）**、v4-pro 1/1；
- 轮数 3/2/2/3/3/3，tokens 3089/1999/1983/3069/3511/3132；
- 对比 E2c（旧提示）0/2；n 小，不宣称显著。
