# P2 — 经验记录（机器可读），以及它**不能**声称的东西

## 1. 这一层做了什么

从**已归档的真实运行**生成两类产物：

| 文件 | 内容 |
| --- | --- |
| `report_*.json` | 结构化 Failure Report（schema `flexcell.failure_report/1`），字段全部复制自该次运行的 `result.json` / `events.jsonl` |
| `experience_place_target.json` | 机器可读经验（schema `flexcell.experience/1`），附带**证据路径** |

生成器：`experiments/pilot-001/pilot/experience.py` + `make_experience.py`。

**防伪机制**（写进代码，不是写进文档）：
- `experience_record()` 在证据文件**不存在**时抛异常，拒绝存储；
- 运行**没有 outcome** 时抛异常，拒绝存储；
- `make_experience.py` 先断言"负例 0 次编辑、正例 1 次编辑"，不满足就不生成经验。

## 2. 四份报告（全部来自真实运行）

| 运行 | 成功 | 迭代 | 编辑 | `list_dir` |
| --- | --- | --- | --- | --- |
| `levelc_prime` | false | 10 | **0** | **33** |
| `c14_inventory` | false | 9 | **0** | **28** |
| `c15_run_b` | **true** | 4 | 1 | **0** |
| `c15_run_c1` | **true** | 5 | 1 | **0** |

## 3. 经验记录的内容（逐字）

```json
{
  "schema": "flexcell.experience/1",
  "defect_class": "stage-transition / target-object selection (place target)",
  "observed": {
    "success": true,
    "iterations": 4,
    "tokens": 16937,
    "behaviour": {
      "tool_calls": 11,
      "by_tool": {
        "edit_file": 1,
        "read_file": 3,
        "read_telemetry": 3,
        "run_execution": 4
      },
      "edited_source": 1,
      "ran_scenario": 4
    }
  },
  "lesson": "When the failure evidence carries the code regions involved, the agent edits them without directory traversal: list_dir fell from 12-28 to 0 and the same defect was repaired in 4-5 iterations instead of never. Naming the file in the task text achieves the same thing, so the cost being removed is LOCALISATION, not reasoning.",
  "evidence": [
    "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/w5_levelc_evidence_20261110/run_b_regions_visible/result.json",
    "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/w5_levelc_evidence_20261110/run_b_regions_visible/events.jsonl",
    "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/w5_levelc_evidence_20261110/run_c1/result.json",
    "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/w5_levelc_evidence_20261110/run_c1/events.jsonl"
  ],
  "provenance": "derived from the run above; not hand-written"
}
```

## 4. 明确**没有**做到的事（对照 24H 目标 §4 的三条区分）

| 目标要求 | 状态 |
| --- | --- |
| ① 人工编写的修复提示 | 存在（Level B 任务文本），已记录 |
| ② Agent 从执行反馈中**自主归纳**的经验 | **未达成**——上面的 `lesson` 是**我（工程师）**从运行中归纳的，不是 agent 自己写的 |
| ③ Agent 后续**真正复用**的经验 | **未达成**——没有任何一次运行读取过 `experience_*.json` |

**因此：本轮不宣称"已开始实现 Experience-Driven Improvement"。**
按目标原文，只有第 ③ 项出现独立证据才能宣称；本轮只交付了"可存储、可核查"的基础设施与一次诚实的归纳。

## 5. 下一轮要补的两步（可执行）
1. 让 agent 在**修复后**自己写一份 `experience`（约束 schema，禁止引用不存在的证据）；
2. 构造**第二个独立缺陷**（不同文件/不同语义，例如 VERIFY 的 zone 解析），
   在任务中提供上一轮的经验文件，测量**迭代数与 token 是否下降**——
   若下降且编辑正确，才是第 ③ 项的证据。
