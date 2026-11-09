# W5-E2e — 第二种故障类型（对象未注册）**3/3 成功（两个模型）**

| rep | model | success | iters | tokens | 目标门 | normal | regrasp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rep1 | deepseek-chat | ✅ | 4 | 4063 | PASS | PASS | PASS |
| rep2 | deepseek-chat | ✅ | 4 | 4060 | PASS | PASS | PASS |
| rep3-flash | deepseek-flash | ✅ | 4 | 4321 | PASS | PASS | PASS |

- 机制与 E2d 不同（注册缺失 vs 目标不可达）；chat 2/2 + flash 1/1。
