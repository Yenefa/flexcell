# GRASP-B-001 Phase 3：逐轮观测门禁与原始日志复核

关联 [#32](https://github.com/Yenefa/flexcell/issues/32)、#13。源码基于
`main@86bb4bd`，运行观测依赖尚待审核的
[PR #50](https://github.com/Yenefa/flexcell/pull/50)，提交
`be6684b30da1eafe80a585f84981a76a511ef48a`。
本次云端工作只验证工具行为；没有新仿真回合，物理根因仍为 **UNKNOWN**。

## 补上的缺口

#50 的下一步是固定 **A1 → A4 → B5**，首轮即检查新观测是否实际生效。
只在每个文件结束后检查，不能阻止 A4/B5 内部在首个缺失记录后继续派发。
`111_grasp_probe.py --require-carry-observation` 现在在每轮原有、已确认的
cleanup 后校验，并在下一次 prepare/PICK 前停批。默认路径仍不启用此门禁。

工具复核动作的真实终态、测量值与 PICK evidence_id、唯一的物体/时间窗口
carry start、session、累计 summary、final 与 stop。它拒绝缺失/重复身份、
不完整终态、harness error、计数不对账、倒退的计数/时间、错误 schema，
以及无法复核的日志。取消 ACK 不能代替动作终态；final 不能代替物理释放。
真实 typed PICK 失败在完整记录和确认 cleanup 后仍是有效观察，不补跑成功。

每轮原始 probe 行新增 `carry_observation`，包含关联结果、计数及读取日志的
大小、SHA-256、起始 byte_offset 和旧前缀 SHA。日志在开始前必须存在且结束于
换行；初始化失败时不启动 ROS。历史前缀保留且不解析，新的损坏行直接停批。
任何旧前缀改写、截断或轮间身份复用同样停批，不清理或修复原始文件。

## 计数范围与解释

- `pick_prefix`：PICK 结束前最近一条 summary 的累计计数，并单列
  `pick_prefix_age_s`。这是截至该采样的前缀，不是精确覆盖整个 lift 的计数。
- `session_totals`：final 的完整会话计数。成功 PICK 的会话还包含后续 PLACE
  的搬回过程，不能把它直接当作 PICK 期间的失败分母。
- `ee_missing_fraction` 仅表示缺失调用次数占比，不是停跟随的墙钟时间占比。
  查询耗时包含阻塞和调度，不等于 TF 年龄；pin 确认也不是箱子物理跟随证明。
- `OBJECT_TIME_UNIQUE_NOT_GOAL_UUID` 明示关联依据。PICK 的 evidence_id 是唯一
  对账入口；旧 motion request_id 及物体名不被当作唯一 goal 身份。

门禁通过只表示该 segment 的记录完整。安装源码、配置/世界摘要、新运行指纹、
strict health、主机负载和完整运动日志仍需单独归档；工具不能从日志代替这些检查。
本工具不授予运行、部署、baseline、路由或 n≥50/AC@90 资格。

## 给仿真电脑 Agent 的手动交接

用户手动转发本节。先审阅 #50 与本变更，准备包含两者的部署版本，记录实际
合成 HEAD 和新指纹。不要重跑已完成的 #47 A5/B5，不启动模型或 GPU 任务。

1. 使用 #47 同一仿真机及既有 teleport 配置，不改 carry 机制、控制器、阈值或
   时序。核对运行中安装的 `carry_server.py` 与 reviewed #50 源码一致；该文件
   SHA-256 为 `1bb5e55ed3f7955389e38fd22921a1837c07c2be86a36009dbfaa5559fe6f7bd`。
   同时核对 111/112 探针与审核的源码。缺版本时停在部署前。
2. 确认没有其他活动任务，strict health 退出 0、`ok=true`、无 hard failures、
   已知 IDLE/carry disengaged。保留 health、配置/世界摘要与主机负载。
   在已加载 ROS 和工作区环境的终端创建一个全新的证据目录。
3. 首段只执行下面的 **A1**；它计入唯一的十轮窗口。每次运行都传
   `--require-carry-observation`，实际日志目录非默认时显式传入两个 log 参数。

```bash
# phase3_dir 由执行者指定为新的空目录；以下命令会发送真实仿真动作。
if python3 setup/111_grasp_probe.py --object target_box_a --trials 1 \
    --require-carry-observation --out "$phase3_dir/A1.jsonl" \
    > "$phase3_dir/A1.stdout" 2> "$phase3_dir/A1.stderr"; then
    echo 0 > "$phase3_dir/A1.exit"
else
    echo "$?" > "$phase3_dir/A1.exit"
fi
```

4. 任一非零退出、harness/观测失败或未知终态，停整个窗口。未知终态不追加
   Place/Reset。其余轮次记 NOT_RUN；不通过换输出文件重跑或补齐。
5. A1 完整后，以新文件名复制完整 `pick.jsonl`、`carry.jsonl` 快照；不截断
   活日志、不覆盖旧快照。执行只读复核（自动使用 probe 中记录的起始偏移）：

```bash
python3 setup/112_carry_observation_gate.py --segment A1 \
    --probe "$phase3_dir/A1.jsonl" --probe-exit "$phase3_dir/A1.exit" \
    --pick-log "$phase3_dir/A1.pick.jsonl" --carry-log "$phase3_dir/A1.carry.jsonl" \
    --out "$phase3_dir/A1.gate.json"
```

6. 仅退出 0 后继续 **A4**（object A、trials 4），再继续 **B5**（object B、trials 5）。
   对各段使用独立 stdout/stderr/exit/probe/完整日志快照，复核命令使用相应
   `--segment A4` / `--segment B5`。段内门禁会在首个证据故障后停止派发；
   段间复核另检查严格轮数、顺序及进程退出状态。段间人工 health 不能被旧
   receipt 代替。本工具不自动编排或证明三段运行的时间顺序。
7. 回传所有原始记录、Pick/Place/carry/motion 日志、health、运行身份、负载及
   SHA 清单。最终完整日志必须保留逐轮 receipt 指定大小以内的原始前缀。
   离线复核重算每份前缀 SHA 和所有展示计数；不会信任行内保存的汇总数字。
   证据不足停批；未复现则保留 NOT_REPRODUCED_IN_THIS_WINDOW 和根因 UNKNOWN。

只读工具退出码：0 = SEGMENT_EVIDENCE_COMPLETE，1 = STOP_INCOMPLETE_EVIDENCE，
2 = STOP_INVALID_INPUT 或不能新建报告。输出文件用排他创建，已有文件不会覆盖。

## 云端验证

```bash
PYTHONPATH=src/flexcell/flexcell_skills python3 -m pytest -q \
  src/flexcell/flexcell_skills/test/test_carry_observation_gate.py \
  src/flexcell/flexcell_skills/test/test_grasp_probe.py
python3 setup/82_undefined_attr_check.py src/flexcell
```

离线验证覆盖真实失败保留、逐轮停批、首轮部署观测缺失、summary/final/
session 的反例、PICK 与 PLACE 计数范围、完整日志的前缀复算和输出不覆盖。
主线基底相关测试 **112 passed**（含 79 项新增），与 #50 合成工作区的相关测试
及原有 loop 差分测试 **137 passed**；静态扫描 37 files / 0 problems。
原始测试日志、JUnit 和源码摘要见
[`grasp_phase3_gate_20261026`](../setup/acceptance/grasp_phase3_gate_20261026/README.md)。
合成输入不能验证真实 TF 时序、磁吸承载故障或插桩开销。完整 ROS CI 与
仿真机运行分别报告，不把本地 Python 检查计作 Gazebo 验收。
