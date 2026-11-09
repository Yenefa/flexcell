# EXPERIMENT MATRIX（本轮 24H 冲刺）

| 任务 | 模型 | 缺陷类型 | 成功 | 迭代 | tokens | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| W5-E2d | deepseek-flash | 可达性（配置） | ✅ | 3 | 3170 | `research/evidence/p0-w5e2d-flash` |
| W5-E2e | deepseek-flash | 对象注册（配置） | ⚠ judge 环境失败 | — | — | `research/evidence/p0-w5e2e-flash` |
| W5-E2c | deepseek-flash | 可达性（旧提示） | ⚠ judge 无效 | 6 | 10688 | `evidence/pilot001-w5e2c` |
| W5-E3 (Level B) | deepseek-flash | **源码**（PLACE 目标区） | ❌ | 6 | 10124 | `research/evidence/p1-w5s-levelb-r1` |
| W5-E3 (Level B) | deepseek-flash | 源码 | ❌ | 6 | — | `.../p1-w5s-levelb-r2` |
| W5-E3 (Level B) | deepseek-flash | 源码 | ❌ | 6 | — | `.../p1-w5s-levelb-r3` |
| W5-E3 (Level B) | deepseek-v4-pro | 源码 | ❌ | 6 | — | `.../p1-w5s-levelb-v4pro` |
| W5-E3 (Level B) | deepseek-flash | 源码（工具已修） | ❌ | 5 | 32802 | `.../p1-w5s-levelb-r4` |
| W5-E3 (Level B) | deepseek-flash | 源码（描述已修） | ⚠ 额度中止 | 2 | — | `.../p1-w5s-levelb-r5` |

## 基线（无 agent）
| 项 | 结果 |
| --- | --- |
| W5-E3 缺陷基线 | dual_object ROBOT_FAILURE；normal PASS；regrasp PASS；build OK |

## Track C（C12，无 agent）
| 场景 | FSM | MTC |
| --- | --- | --- |
| A | 2/2 | 2/2 |
| B | 0/2（安全门） | 0/2（安全门） |
| C | 2/2 | 2/2 |
