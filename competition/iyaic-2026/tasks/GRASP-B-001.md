# GRASP-B-001-PHASE-1：给仿真电脑 Agent 的执行任务

**状态：历史窗口已完成，以下方案仅留档，不再次执行。** #47 已归档 A5/B5，结果为该窗口未复现。
下一步先部署 [PR #50](https://github.com/Yenefa/flexcell/pull/50) 的 teleport 查询观测；
后续使用其中的新版本/新指纹 Phase-3 任务，第一轮即检查计数是否实际可用。

在已有 ROS 2 / MoveIt / Gazebo 仿真电脑上执行（当前指定的 RTX 5060 Ti 16GB 电脑）。
这轮直接诊断 Pick/Place Skill，不调用 Clef、付费模型或 PyTorch，不需要家用 GPU 服务。
云端准备代码和任务，用户手动转发本文件，电脑 Agent 返回原始产物。

## 任务身份与现状

- 固定运行源码：`main@36486780f5bf46add81124aa334400c71be4ae72`。
- 复用 main 的 `setup/111_grasp_probe.py`（#29 已合并）；issue 中提到的 `136_grasp_diagnostic.py` 是另一分支的工具，不是本轮入口。
- [云端历史复核](../evidence/grasp-failures-20261025.json)：三份 E-021 baseline 的 6 个失败任务中，有 12 次 PICK 返回 23，全部报告 `box did not follow the lift`；B 8 次、A 4 次，任务最后均为 51。
- 这是失败任务子集，不是 60 回合里所有 PICK 失败的清单，也不是失败率。原始三份 batch、六份 episode 与 SHA 均保留。
- 这份初稿只看了 native 切片；#47 后续已回收本机阶段日志，并匹配上述 12 个 PICK。当前缺口是 teleport 的 TF 查询缺失与 pin 请求分母观测，物理根因仍 UNKNOWN。显示成 `0.030m < 0.030m` 的一条是舍入文本，不能据此改阈值。

## 先回收已有证据

先用上述 JSON 的 12 个 `evidence_id` 在现有 `pick.jsonl` 和已封存本机日志中定位。
找到了就按原字节复制，关联对应 request_id 和 motion 日志；没找到记 MISSING_IN_THIS_HOST，不能推断别的机器从未产出。
如果本机已有本任务同源码、同指纹、相同 A5/B5 条件的完整回执，直接返回，不重跑。

## 执行前条件

1. 保留工作区修改和既有 baseline；确认没有其他任务正在操作这套仿真。若在运行，返回 BUSY，不能为本任务停止它。
2. 记录 git HEAD、diff、运行 overlay 来源、配置/世界摘要、carry backend 和运行指纹。核对上述固定源码已构建并被实际加载；用现有本机流程构建，不能把旧 install 当新代码。
3. 使用已有 WSL/ROS 环境和已验收物理配置。若缺源码或环境，回传具体缺失；公用电脑不要求登录 GitHub，不改系统、驱动或网络。
4. 现有栈可用就复用；无任务且栈未启动时，按本机既有流程启动。严格 health 必须退出 0、顶层 `ok=true`、`hard_fail=[]`，并另确认 `checks.task_state=IDLE`、`checks.carry_engaged=false`。未知承载状态不能靠一次 Reset 消除证据。
5. 若配置与已验收 profile 不一致，回传 CONFIG_MISMATCH。冻结 carry 后端、容差、阈值、恢复预算和时序不改；不插桩或调参后补采到绿。

## 固定窗口：A5，然后 B5，最多 10 轮

研究问题：在每轮 canonical reset、清除注入后，当前单物体 Skill 能否出现同类低 rise？
它只诊断这个条件；不复现双物体 A→B 的完整上下文，也不是 FSM/Hybrid 对照或资格 smoke。

进入仓库根目录，source 已有 ROS/overlay 环境。创建全新的输出目录并记录路径，不能覆盖旧文件。
下面创建 `task_out` 新目录。先运行 A，保留 stdout、stderr 和真实退出码：

```bash
mkdir -p "$HOME/.ros/flexcell/diagnostics" || exit 1
task_out=$(mktemp -d "$HOME/.ros/flexcell/diagnostics/GRASP-B-001_XXXXXX") || exit 1
if python3 setup/111_grasp_probe.py --object target_box_a --trials 5 \
    --out "$task_out/A.jsonl" >"$task_out/A.stdout" 2>"$task_out/A.stderr"; then
  probe_a_rc=0
else
  probe_a_rc=$?
fi
printf '%s\n' "$probe_a_rc" >"$task_out/A.exit"
```

只有 A 返回 0、JSONL 恰有 5 行且无 `harness_error`，才执行 B；否则 B 标 NOT_RUN 并停批。
下面的条件保留 A 的退出码和完整行数要求，同样记录 B 的 stdout/stderr/exit：

```bash
if [ "$probe_a_rc" -eq 0 ] && python3 - "$task_out/A.jsonl" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as stream:
    rows = [json.loads(line) for line in stream if line.strip()]
raise SystemExit(0 if len(rows) == 5 and all(not r.get('harness_error') for r in rows) else 1)
PY
then
  if python3 setup/111_grasp_probe.py --object target_box_b --trials 5 \
      --out "$task_out/B.jsonl" >"$task_out/B.stdout" 2>"$task_out/B.stderr"; then
    probe_b_rc=0
  else
    probe_b_rc=$?
  fi
  printf '%s\n' "$probe_b_rc" >"$task_out/B.exit"
else
  printf '%s\n' 'NOT_RUN: A did not complete its fixed window' >"$task_out/B.not-run"
fi
```

脚本自身已做每轮 reset、注入清除、确认终态和已知终态后的 cleanup。不要额外补发 goal。
真实 typed PICK 失败可作为观测保留并继续预定窗口；CLI 退出 0 仅表示没有 harness error，不表示所有抓取成功。
接受/终态未知、取消未确认停止、释放或 reset 不确认时，保留部分 JSONL，停止整个任务；不能再跑 B、Place 或 Reset。
取消 ACK 不是终态。原始失败不丢弃，不另开窗口替换，也不追加 S1、S7 或大样本。

## 阶段日志和待证伪假设

同时保留这段执行的原始 `pick.jsonl`、`place.jsonl`、`carry.jsonl`、`move_to_pose.jsonl`、fleet/ROS 日志以及运行前后的严格 health 回执。
优先以探针返回的 `evidence_id` 找 Pick/Place 记录，再用 Pick 的 request_id 关联 hover/grasp/lift motion。
goal UUID 也保留，但不能仅凭相邻行就宣布关联。carry 只有物体和时间的候选关系时标 AMBIGUOUS；缺少字段记 UNKNOWN，不新增冻结后端的 telemetry。

| 假设 | 本轮需要的已有证据 | 不能由缺失推出的结论 |
| --- | --- | --- |
| 接近/附着阶段异常 | attach_gap_m、carry_offset、scene fallback、engage 确认（仅对应 backend） | 没有错误日志不等于 attach 正常 |
| 抬升执行异常 | lift 的请求/终态、错误码、已有末端或 controller 测量 | task 的动作名不证明控制器到位 |
| 承载跟随不足 | 同物体的 carry 事件、已有 session、box_before/after、box_rise_m | 全局显卡使用或模型提案不能解释承载效果 |
| 位姿采样/时序问题 | 已有采样时间、观测身份、motion 与 carry 的时间窗 | 没有时间戳不能证明样本新鲜 |

把日志按字节复制到回传目录；记录来源路径、采集时间、大小和 SHA-256。
仍在追加的日志标为 SNAPSHOT 并记录截取字节数，不声称它等于源文件的最终 SHA。原文件不清空或格式化。

## 回传

提供一个 ZIP，包含代码/部署身份、A/B JSONL、stdout/stderr/退出码、完整失败记录、阶段日志、health、文件 SHA 清单。
同时给一张逐轮表：对象、trial、goal UUID、evidence_id、outcome/error、rise、attach gap、carry 确认、lift 终态、cleanup 和关联完整性。无值显式 UNKNOWN。

结论只写：REPRODUCED / NOT_REPRODUCED_IN_THIS_WINDOW / BLOCKED，并列证据与尚不能区分的假设。
即使 10 轮全成功，也保留 UNKNOWN 根因和不同试次条件，不能宣布 E-021 已修复或解除 n≥50 冻结。
结束时仅处理本任务拥有且已确认动作停止的进程；复用的既有栈保持原有归属。
