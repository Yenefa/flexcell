# E-016 — 启动、carry 权威状态与模型评估主线（2026-10-02）

本轮修复了启动路径、控制器就绪探测和 carry 输入污染，补上本地真实模型配置、置信度校准及离线重放入口，并把既有主线和证据提交到本地 `main`。**未 push。当前部署选择 FSM，reset / strict health / carry 新鲜度探针均通过；Hybrid 在线验收没有通过。** 这不是新的统计基线。

证据根目录：[hardening_20261002](../setup/acceptance/hardening_20261002/)。机器摘要见 [summary.json](../setup/acceptance/hardening_20261002/summary.json)，文件散列见 [manifest.json](../setup/acceptance/hardening_20261002/manifest.json)。最终实现源码提交 `525097d`；部署以 `deployment.json` 内的源码散列为准，不能只按 Git HEAD 推断运行内容。

## 八项缺口的处理结果

| 项目 | 已落地的处理 | 验收及边界 |
| --- | --- | --- |
| 1. 消失的 F: 路径 | `setup/flexcell` 从脚本真实位置计算仓库路径，默认使用仓内 `worlds/` 和 `setup/`；保留 `FLEXCELL_WORLD` 显式覆盖，脚本可执行 | 实际冷停/冷启动通过；仍需安装 ROS 和 build overlay |
| 2. 启动探测走 ROS CLI | `117_ros_ready.py` 直接调用 `controller_manager_msgs/srv/ListControllers`，逐项检查三个控制器的 `active` 状态，使用有界期限 | 冷启动显示 `START OK`，最终 strict health 全部通过；不再经 `ros2 control list_controllers` |
| 3. A 的 carry 泄漏到 B | 新增 `QueryCarry.srv`；Observe 每次决策快照查询 `/flexcell/carry_snapshot`，不复用 topic 缓存。服务串行读取 ROS 所有权，并核对 native carry 状态 | 实际注入 `engaged=true,target_box_a,stamp=0`，Observe 返回 `engaged=false,object_id=''`。查询失败使 Observe 失败，不能伪造“未抓取” |
| 4. CRLF | 先提交语义主线，再单独落实 LF 属性；保留原显式规则及 binary 规则。acceptance 和原始 setup 日志禁止换行转码 | 历史日志已恢复原字节；原始证据 454 项在 Git 和工作区均匹配 manifest |
| 5. 脏工作区 | 原有策略、carry、客户端、C++ 插件和证据先完整 checkpoint，后续修复分开提交 | 本地提交，无 push；不覆盖并发工作，不删除失败记录 |
| 6. 离线 model replay | `119_policy_eval.py` 用已存 canonical 输入调用冻结本地模型；固定权重、运行时、解码参数及实际导入源码散列，区分 counterfactual 和 same-model | 5 个历史输入的 counterfactual 已完成；1 个派生 fixture 的同模型重放已完成且 **FAIL**。历史 DeepSeek 同模型重放仍 NOT_RUN |
| 7. Jev 端点和校准 | 安装并启动 SHA 固定的真实本地 Qwen 1.5B / 3B；收集 Jev 分回合训练/留出数据，校准绑定权重、模型名及 prompt。Hybrid 仅允许经校准的快路径 | 4/30 校准样本匹配 FSM 动作，留出 1/5；校准下界 0.0531，达不到 0.7，故 Hybrid 跳过无资格的快路径并进入官方 DeepSeek |
| 8. reset139 / gate_flood | admin 的父进程必须等待 native worker 正常退出后才承认成功；Gazebo pose 解码移入独立纯 Python protobuf worker，使用 raw 订阅、20 Hz 原生限流和退出清理 | 真实 SIGSEGV 子进程即使先输出 `ok:true`，父进程仍返回失败。历史崩溃根因和 flood 的原始触发源均保留 **UNKNOWN**，本轮健康不能代替根因证明 |

`carry_snapshot` 的 native status 是只读查询。允许最多三次、每次 400 ms 的传输重试；总 native 等待小于 Observe 2 s 的 ROS 等待。所有权不匹配立即拒绝，不会为了可用性把未知 carry 改成 off。新增两项回归验证丢一次回复和丢全部回复，5 项 carry snapshot 测试通过。

## 实际机器人运行记录

全部使用 protocol v2，摘要和 episode 原文件均保留。每次切换有独立运行指纹，下面的结果不能合并成某个版本的成功率。

| 批次 | 实际结果 | 主要证据 |
| --- | --- | --- |
| `025125` Hybrid | FAILED；PICK A 成功，PLACE 的规划服务不可用 | `batches/batch_20261002_025125.jsonl` |
| `030038` FSM | SUCCEEDED；双物体全闭环，8 个决策精确重放。45.77 s，A 误差 2.11 mm，B 14.81 mm | `batches/batch_20261002_030038.jsonl` |
| `030415` Hybrid | 客户端 150 s 超时，原批次 HARNESS_ERROR；稍后服务器入库 CANCELED，完成 A 的 PICK/PLACE/VERIFY，未开始 B | 原批次、late episode 和 `late_episode_correlation.json`；未追改批次结果 |
| `032332` Hybrid | FAILED；native carry status 查询超时使首次 Observe 失败 | `batches/batch_20261002_032332.jsonl` |
| `033019` Hybrid | FAILED；快模型按校准旁路，官方模型请求超时后明确退回 FSM；PLACE 的 goal 首次应答/服务可用性失败，任务中止 | `batches/batch_20261002_033019.jsonl` |

最后部署为 FSM，运行指纹 `0717a0db1abb86d982756fa8e4880e120caabf89f60cd462f499ae89ec0a6813`。最终 reset RC=0/ok=true，strict health RC=0/IDLE/carry off，真实旧 carry 注入探针 RC=0。**最终指纹没有新增机器人 S1 回合**；前述成功 S1 是较早指纹的闭环证据。

官方慢路径仍是用户授权的 `deepseek-flash`，没有用本地小模型冒充或替换在线慢路径。本地 3B 只用于离线 counterfactual / frozen fixture 评估。末尾的最小鉴权请求经代理 20.210 s、直连 20.173 s 都 TimeoutError；直连未鉴权根路径 0.241 s 返回 401。该对照说明公开 HTTPS 可达、鉴权 completion 在本次两种路径上均未返回，**不能据此定位供应商内部原因**。

同一持久五元预算账本现在有 163 项记录，保守累计上界 **¥1.168980**；其中 6 项 `RESERVED_OR_UNKNOWN` 仍占预算，不按“超时没结果”退款。本轮不再重复付费请求。[预算快照](../setup/acceptance/hardening_20261002/budget_snapshot.json) 仅包含用量和请求标识，密钥保存在仓库外的 mode-600 文件。

## 离线重放和校准，结论分别是什么

离线工具不调用 ROS，不重放动作，不消耗官方 API 预算。它核对拥有的 loopback llama-server 进程参数、权重与 runtime archive 的 SHA256。两个本地模型均是真实权重；fast 为 Qwen2.5-1.5B Q4_K_M，slow 为 Qwen2.5-3B Q4_K_M，运行时 llama.cpp b11284 Linux CPU。

- 5 个旧 E-015 输入共有 41 步，36 次本地模型调用，19 次有效模型输出，15 步语义一致（包含 5 步无需模型的 bootstrap）；其余模型退回 FSM 的输出不算模型成功。这是 **COUNTERFACTUAL_MODEL_EVALUATION**。
- 从第一遍实际输出派生的 `MODEL_INPUT_FIXTURE` 没有 executor result，最终状态是 `NOT_EXECUTED`。选择其中 1 个 fixture 做同冻结模型重复：10 步中 4 步一致、9 次调用仅 3 次有效输出，6 步差异或不可用，**SAME_FROZEN_MODEL_REPLAY = FAIL**。160 token cap 下出现输出截断/解析失败，这些失败未删除。
- `95_metrics_report.py` 核对冻结 identity、源文件散列、步骤编号和原决策，再独立重算语义比较；不盲信结果文件的 `ok`。fixture 只报告 model replay，机器人成功率、物理和安全验证为 NOT_RUN。
- 旧 DeepSeek episode 没有不可变权重身份，不能靠 Qwen 的结果填绿，也不能把 fixture 当新机器人样本。
- Jev 35 个可用输入以回合分割，1 个超出 FSM grammar 的输入排除。校准集 4/30 匹配，95% Wilson 下界 0.053095694；留出 1/5，5/5 输出格式有效。标签仅为 **FSM_ACTION_AGREEMENT**，不是物理成功概率。原始置信度 0.9–1.0 明显不能直接拿来路由。

原始校准采集文件没有改写；部署校准文件单独记录原文件 SHA 和 prompt AST 身份迁移。任何替代 transport 的输出不能继承真实权重的校准。缺失/不支持校准或阈值不可达时，Hybrid 会记录 `calibration_unavailable_or_threshold_unattainable` 并跳过 fast 调用。当前 Hybrid 的实际有效路径仍是 DeepSeek，快路径能力没有验收通过。

冻结评估时的策略源码保存为 `frozen_replay_source.zip`。后续给 LLM 增加错误类型诊断会改变源码身份，因此重现这次重复评估应导入该 archive 的源码；工具现在散列实际导入包。`source_snapshot.zip` 则保存本轮最终实现，两者不得混为一份。

## 入口和重现命令

以下从仓库根目录执行。ROS/overlay 构建仍是前提；密钥、模型权重和 llama runtime 均在仓库外。

```bash
source setup/104_mainline_env.sh
./setup/flexcell start
./setup/flexcell reset
./setup/flexcell health
```

`engage_carry` 的具体入口是包 `flexcell_skills` 中节点 `carry_server`，实现 `carry_server.py`，`week1.launch.py` 会启动它；ROS 服务实际名为 `/flexcell/carry_engage`，查询服务为 `/flexcell/carry_snapshot`。速度约束 backend 还需 build `flexcell_gazebo`、选择仓内 `worlds/flexcell_velocity_servo` 并设置 `FLEXCELL_CARRY_BACKEND=velocity_servo`，否则默认 world 仍使用声明过的 teleport backend。当前私有 physics profile 和部署 world 的非密钥快照已存证据目录。

新鲜度调查入口是 `setup/121_carry_freshness_probe.py`（必须 IDLE 且确认 carry off）。接收 topic 的 `_carry` 仍可用于诊断，但 `_current_carry()` 构造世界快照时查询权威服务；`observe.jsonl` 的 `carry_snapshot` 记录含请求/回复 monotonic 时间、revision/session、topic 缓存及 native 查询次数。

```bash
python3 setup/121_carry_freshness_probe.py
python3 setup/120_pose_lifecycle_probe.py --out /tmp/pose_lifecycle.json
python3 setup/118_local_models.py install
python3 setup/118_local_models.py start
python3 setup/118_local_models.py status
PYTHONPATH="$PWD/src/flexcell/flexcell_skills:$PYTHONPATH" \
  python3 setup/119_policy_eval.py calibrate \
  --episodes setup/acceptance/hardening_20261002/recorded_inputs \
  --out /tmp/jev_calibration_new.json
PYTHONPATH="$PWD/src/flexcell/flexcell_skills:$PYTHONPATH" \
  python3 setup/119_policy_eval.py replay \
  --episodes setup/acceptance/hardening_20261002/recorded_inputs \
  --out /tmp/counterfactual_new.json --make-repeatability-fixtures
```

要复现原冻结 fixture，先把 `frozen_replay_source.zip` 解压到临时目录，再把其解压根目录放在 PYTHONPATH 最前；保持本地 slow-server 参数与该次 freeze 一致。下列评估仍会实际推理，可能耗时数分钟；不是本轮又重跑了一次的声明。

```bash
unzip -q setup/acceptance/hardening_20261002/frozen_replay_source.zip -d /tmp/flexcell-e016-frozen
PYTHONPATH="/tmp/flexcell-e016-frozen:$PYTHONPATH" \
  python3 setup/119_policy_eval.py replay \
  --episodes setup/acceptance/hardening_20261002/replay_fixture_one \
  --out /tmp/same_model_new.json
python3 setup/95_metrics_report.py \
  --store setup/acceptance/hardening_20261002/replay_fixture_one \
  --model-replay-results /tmp/same_model_new.json
```

## 测试范围、历史根因及下一门槛

完整 skills pytest：193 项、0 failures/errors/skips；覆盖真实执行器控制流与契约，ROS 行为通常用替代调用，不等于 Gazebo 抓取可靠性。另跑 carry snapshot 5 项（含 2 项新传输丢失回归）全部通过。interfaces / skills build 通过；最新 skills build 7.66 s。实际机器人结果和真实崩溃子进程测试单列，不把两类证据混算。

Gazebo 已安装 Python callback shim 会在异常路径执行 `print(traceback.format_exc(), sys.stderr)`；这把 stream 当成打印对象，持续异常会被放大到 stdout。新 raw 订阅 worker 不经过该解码 shim，解码和 native callback 也不再驻留 ROS/admin 父进程。这解决了明确的传播与隔离问题，**原历史异常触发源仍 UNKNOWN**。对旧 typed subscriber 的 C++ / pure-Python protobuf 各 3 次、每次 100 消息控制，共 600 个回调零错误/零崩溃；该搜索范围没有复现历史完整 ROS shutdown 工作负载，不能用来宣称根因关闭。

E-014 已有 Fast DDS 分片路径证据，但历史 Cyclone GetResult 首次回复丢失未在其 352 个虚拟 goal 中复现。客户端对同一 accepted goal 重读结果只覆盖结果响应丢失；本轮 PLACE 的 SendGoal 未应答/服务不可用不能由它保证解决，也不能重发可能执行中的物理动作。此项仍需针对在线完整管线的服务/发送/接受日志继续收敛。

协议裁决保持不变：E-011 为 protocol v1 存档；新批使用 v2 和完整运行指纹。既有三个假延迟报告的 NOT_RUN 更正保持原状态，本轮没有再生成历史数字。原证据 Git 换行转码已恢复，[454 项原字节核对](../setup/acceptance/hardening_20261002/archived_evidence_bytecheck.json) 全部通过。

n≥50/100 和 400 回合方案 **未启动**。下一主线门槛是官方 completion 恢复后，先把 Hybrid 同指纹 n=5 跑通，并单独解决服务/SendGoal 可用性失败；不能拿本轮不同指纹的失败与 FSM 单次成功拼一个基线。MTC 和 rosdep 闭包继续保持未完成/NOT_VERIFIED。
