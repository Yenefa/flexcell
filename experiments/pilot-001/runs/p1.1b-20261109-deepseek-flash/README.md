# P1.1b 真实 LLM 三臂试跑（deepseek-flash，2026-11-09）

- 模型 `deepseek-flash`（显式设置；系统环境变量中 `FLEXCELL_PILOT_MODEL` 仍未持久化）。
- Key 仅以指纹记录，无明文。任务仍为玩具夹具（**仅验证链路，非研究数据**）。

| 臂 | success | false_success | 轮数 | tokens | 证据完整度 |
| --- | --- | --- | --- | --- | --- |
| A | true | false | 2 | 848 | 0.5 |
| C | true | false | 2 | 983 | 0.5 |
| B | true | false | 2 | 1003 | 0.5 |

结论同 p1.1：玩具任务不区分三臂（均靠单元测试解出，未调用执行工具），不能用于 C−A / B−C 分析。
