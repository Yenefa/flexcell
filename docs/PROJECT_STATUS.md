# PROJECT STATUS — 单一事实来源（2026-11-09）

> 本文件汇总**当前**成熟度与证据；发现与旧文档冲突时，以本文件 + 证据文件为准。
> 统计口径见 [`STATS_AUDIT.md`](STATS_AUDIT.md)；三 Track 计划见 [`TRIPLE_TRACK_PLAN.md`](TRIPLE_TRACK_PLAN.md)。

## 1. 工作包成熟度
| 工作包 | 成熟度 | 关键证据 | 限制 |
| --- | --- | --- | --- |
| W1 自主开发 | **M3-S**（三类真实任务 n=3） | `runs/p1.4-tg1-reliability-20261109/`、`p1.4-tg3-20261109/`、`p1.4-tg4-20261109/` | 单模型、缺陷人工注入；M3-R 未达 |
| W2 技能与组合 | M3-S（组合任务 3/3） | `runs/p1.4-tg4-20261109/` | 组合仅双对象 |
| W3 运行时 Agent | M3-S | Track C 证据、P1.2 对照 | 单模型 |
| W4 证据与复现 | M3-S | 全量 episode/fingerprint/`verify.py` | — |
| W5 自改进 | **M3-S 级实验**（真实层 E2b 3/3、E2d 5/5（两模型）、E2e 2/2（第二种缺陷）；合成层 W5A） | `runs/p1.5-w5e2b-20261109/`、`p1.5-w5e2d-20261109/` | 单模型、缺陷人工注入；E2c 0/2 已记录 |
| W6 跨场景迁移 | M3-S（n=3，探索性） | `runs/p1.5-w6-transfer-20261109/` | Cold 0/3 vs Warm 2/3，p=0.4 |
| W7 跨本体 | **M0（设计，BLOCKED）** | `docs/W7_CROSS_EMBODIMENT_DESIGN.md` | 无第二本体 |

## 2. Track C（FSM vs MTC）结果
| 实验 | 场景 | 结果 | 备注 |
| --- | --- | --- | --- |
| C3 | normal n=3 | 3/3 vs 3/3；MTC +22.9% wall | 探索性 |
| C4 | dual_object n=3 | 3/3 vs 3/3；MTC +20.4% | 探索性 |
| C5 | recovery_once n=3 | 3/3 vs 3/3；MTC +14.5% | 两臂均 1 次 RECOVERY |
| C6 | normal n=9 | 9/9 vs 9/9；MTC +16.9% | 方向与 C3 一致 |
| C7 | normal 2 cm n=3 | 3/3 vs 3/3 | 收紧容差未区分 |
| C8 | dual_object 2 cm n=3 | 3/3 vs 1/3 | Fisher p=0.4，不显著 |
| C9 | dual_object 2 cm n=9 | 9/9 vs 6/9 | Fisher p≈0.206，不显著 |
| C10 | 机制归因 | 3/3 失败=planning timeout+busy | 6/6 成功无 |
| C11 | 修复评估 | 目标 5/5（基线 6/9）；FSM 3/3；默认 MTC 4/4 | 排程 5/3/4（预注册 6/3/3，已披露） |

## 3. 自改进闭环（W5）现状
- **合成层**：W5-E1 W5A 成功（4 轮，目标+回归门），W5B 失败；
- **真实 Gazebo**：W5-E2 3 次失败 → BLOCKED（预算全用于探索）；W5-E2b **3/3 成功**（单回归门）；
- **多场景回归门**：E2c 0/2（旧提示）→ **E2d 2/2**（显式行动指令）；
- **行动缺口**：8/8 失败样本零写操作；E2d 首写前读取 2 次。

## 4. 关键未决
1. MTC 50 Hz 规划超时的修复仅为有界重试；更大 n 与第二场景未验证（C12）；
2. W5 均单模型；第二模型（deepseek-v4-pro）与第二种故障类型待做（P0）；
3. W7 无第二本体，M3-R 未达；
4. 旧文档中的统计错误已在本轮修正，见 `STATS_AUDIT.md`。

## 5. 复现入口
- 单元测试：`pytest experiments/pilot-001/tests -q`（29）与 `pytest src/flexcell/flexcell_skills/test/test_mtc_motion.py -q`（32）；
- 证据校验：各 `setup/acceptance/*/verify.py` 与 `runs/*/verify.py`；
- 演示：`docs/COMPETITION_DEMO.md`。

## 模型口径（2026-11-09 项目负责人更正）
- `deepseek-flash` 即 **DeepSeek v4.1 Flash（1017）**，是当前主力/最强模型；API 只暴露该 id（无版本化别名）；
- `deepseek-v4-pro` 为较早的重模型对照，不再当作"更强"；
- `deepseek-chat` 为早期默认，仅作跨版本稳定性对照。
