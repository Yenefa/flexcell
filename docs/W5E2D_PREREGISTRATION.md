# W5-E2d 预注册 — 显式行动指令下的多场景自改进（冻结草案）

> 依据：`docs/W5_ACTION_GAP_ANALYSIS.md` 显示 8/8 失败样本均未写文件；E2c 阅读 31 次。
> E2d 只改 task.md，检验"显式行动指令"能否让 agent 落笔。

## 1. 与 E2c 的唯一差异
| 项 | E2c | E2d |
| --- | --- | --- |
| 场景/门/预算/缺陷 | dual_object + normal + regrasp；6 轮；zone_2=0.45 | **完全相同** |
| task.md | "修 config/week1.yaml" | 增加："先运行目标场景一次；**不要**检查 gate/ 或其他文件；然后直接编辑 `config/week1.yaml` 的 `zone_2_x`" |

## 2. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | 三门全 PASS（verified improvement） |
| 过程指标 | 是否写、首写前 read/list 次数、迭代、token |

## 3. 判读规则（冻结）
- 写且三门 PASS → 记"显式行动指令可改变行为（n=1）"；
- 仍不写 → 记为**模型行为限制**，不再加提示/预算；
- 不得修改门/容差/世界；
- 最多 2 次试点，之后无论结果都停止该线。

## 4. 记录
- `experiments/pilot-001/runs/p1.5-w5e2d-20261109/`。

## 5. 结果附录（运行后追加，不改规则）
- **2/2 成功**：轮数 3/2、tokens 3089/1999、首写前读取 2/2；
- 每轮三门（目标 dual_object + normal + regrasp）均 PASS；
- 对比 E2c（0/2、阅读 31 次、未写）→ 显式行动指令改变了行为；
- 记录：`runs/p1.5-w5e2d-20261109/`（含 verify.py）。
