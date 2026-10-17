# 两个候选比赛场景

状态：**SCRIPT_DRAFT / LIVE_ACCEPTANCE_PENDING**。本文件不是机器人执行入口。

## 场景一：失败可见、恢复有界的柔性搬运

应用叙事：小批量工位搬运在一次抓取异常后如何继续，并能向操作者说明结果。

- 复用 main 的 S1 正常链、S2(A)/S3(B)一次注入、S5持续故障。
- 演示：预检与canonical初态 → Observe → Pick → 一次注入失败 → Reobserve → 预算内重试 →
  Place → 独立Verify；持续失败作为附加片段，展示错误与预算耗尽停止。
- 屏幕显示真实来源、错误码、剩余预算和实测位置，模型提案与物理成功分开。
- FSM也有恢复能力；这证明系统机制，不证明模型独有优势。

正式执行前固定一个场景、fingerprint、物理后端和已验收脚本，不在台上临时调阈值。

## 场景二：有缓冲位的A/B交换

依赖尚未合入 main 的 TransferBench 组合任务能力；先完成接入与新身份验收。
链路：B→缓冲位、A→B原位、B→A原位，最后同时验证最终A/B位置、缓冲位空置与carry释放。

- 外层三段顺序由调用者提供；模型仍只决定段内动作。
- 展示重复访问B、复用原子Skill、整链机械臂所有权和联合终态核验。
- 附加暂停续跑只在已确认、已提交且carry释放的段边界进行；旧前缀不重复执行。
- 未知尾部、失败、取消或未确认动作终态不能授权续跑；不称运动中崩溃恢复。
- 一条完整交换是一个逻辑任务，三个component episodes不能当三个独立成功样本。

[分支接口与边界](https://github.com/Yenefa/flexcell/blob/01fd76f/docs/COMPOSITE_TASKS.md)

## 现场准入表（每次固定演示版本填写）

| 项                                                       | 当前值               |
| -------------------------------------------------------- | -------------------- |
| commit/tag、runtime fingerprint、protocol、carry backend | UNKNOWN / NOT_FROZEN |
| 模型/权重/校准身份、真实最小推理                         | NOT_VERIFIED         |
| 启动、严格健康、canonical reset、IDLE/carry释放          | NOT_RUN              |
| 固定窗口内演练次数、通过规则、全部失败位置               | NOT_REGISTERED       |
| 冷启/断网/投影分辨率验收                                 | NOT_RUN              |
| 视频/历史回放离线可用                                    | NOT_RUN              |

准入规则和次数在演练前固定，不循环挑成功子集。未知动作终态立即停止，先确认所有权及现场状态；
不为了继续展示补发物理goal、Place或Reset。

展示模式必须显式标为 LIVE_MODEL、LIVE_FSM、RECORDED_VIDEO、EVIDENCE_REPLAY 或 SYNTHETIC_ILLUSTRATION。
若现场Hybrid未验收，使用FSM实时演示及真实Hybrid录像/证据回放，各自标注；不能冒充在线模型。
