# 学校笔记本 clef 校准与真实路由验收（2026-10-06）

本机生成并接入 Clef-Flash-Q8_0 校准，`route_eligible(0.85)` 为 true。
冷启动 `hybrid 0.85` 后，单对象真实 episode 的 PICK、PLACE、VERIFY
均由 clef 接管，三次调用合计 4,123 tokens，DeepSeek 选择次数为 0，
最终 `outcome=0`、`error_code=0`、安全拒绝为 0。

权威构建与运行工作区为 `/home/ros/agentic_workcell_ws`，运行源码 HEAD
为 `ffde775a0ef9d1cb0f6a3b39436fbe1f97927370`。运行时导入包位于
`~/.local/share/flexcell/mainline/install`；校准前核对了实际导入包的
prompt digest 与权威工作区源文件字节哈希。环境为 ROS domain 45、
`rmw_cyclonedds_cpp`，保留字面 IP 的 no_proxy 和 45 秒 clef timeout。

## 校准输入、划分与身份

从最新一个具有至少 5 个 episode 的同指纹 S1 历史组中选取全部 5 份输入，
包括历史失败，原始指纹为
`4381dad6aa575478551630ee51c90bfacf83675614375fba30d402ad71420690`。
历史模型输出不作为标签：使用本机 FSM 重算 action，调用当前 clef 做
counterfactual evaluation。它不表示历史模型的同模型重放，也不表示物理成功率。

输入按文件名排序，index `% 3 == 2` 的完整 episode 留出，其余用于校准。
先评估前 3 份，再只评估剩余 2 份；没有重采、没有重复输入、没有跨指纹混池。
`assemble_calibration.py` 逐行复核标签、身份、原始输入散列和划分，保持原始
latency 与错误，再使用 `119_policy_eval.py` 的相同 bin 与 Wilson 算法重算。

| reported confidence bin | 校准 n | action 一致数 | Wilson 95% 下界 |
| ----------------------- | -----: | ------------: | --------------: |
| [0.0, 0.5)              |      2 |             2 |        0.342372 |
| [0.5, 0.8)              |      5 |             1 |        0.036223 |
| [0.8, 1.0]              |     23 |            23 |    **0.856879** |

总计 35 次实际推理；另有 1 条输入处于 FSM grammar 外，记录为 excluded。
留出集 5 次调用全部返回有效模型结果，action 一致为 4/5。全部 5 条误判
（校准集 4 条、留出集 1 条）均保留，都是低置信度的 OBSERVE→PICK 误判。

pilot CLI rc=0，但高 bin n=13、下界 0.771898，明确未达路由门槛。
extension CLI rc=1，因为该分段没有 heldout；其原始有效预测被保留，
不会把 rc=1 宣称为验收成功。合并后的 heldout 沿用 pilot，划分等同一次
对完整 5 份输入运行生成器。最终判断以 bins、身份和真实路由 JSON 为准。

- `model`: `clef-flash-q8_0`
- `model_sha256`: `8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9`
- `prompt_sha256`: `b37e71cd0b9b0ff81cfa3638111da8375251be2fadeabc01468ce46b5f4e85b8`
- `schema_version`: 1；`label_definition`: `FSM_ACTION_AGREEMENT`
- 校准文件 SHA256：`34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`
- 本机 profile 引用：`/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json`

文件名沿用既有 teardown 验证脚本的硬编码要求；实际生成日期为 2026-10-06。
profile 修改前备份位置见 `run/activation.json`，不包含凭据。

## 真实单对象 episode

`run/live_audit_verified.json` 为最终单对象审计。run ID 为
`pick_place_v1-a0d14046`；部署指纹为
`0bc2bb56e6bb9128fbd43da410ab3870ad7a3b439cec01f8ba95fbc872b9ddf4`。

| 决策                 | source | fallback | measured tokens |
| -------------------- | ------ | -------- | --------------: |
| OBSERVE（bootstrap） | fsm    | true     |      不调用模型 |
| PICK                 | jev    | false    |            1327 |
| PLACE                | jev    | false    |            1375 |
| VERIFY               | jev    | false    |            1421 |

所有非 bootstrap 的 jev 提案均未 skip，模型与校准身份一致，
`confidence_calibrated=true`、`escalated=false`、安全门通过。
`audit_routing_episode` 复算通过，并逐字段对照顶层平铺 `decisions.jsonl`
与 episode。episode serializer 将浮点数舍入到 9 位，比较使用其实际
`_sanitize` 规则，未放宽模型身份或 token 判据。

模型决策延迟使用源码中的 `perf_counter_ns` 测量，保留浮点毫秒，
排除 bootstrap：p50 1773.520879 ms、p95 1847.600272 ms、
max 1855.831316 ms。单次物理误差为 1.183484 mm。
reset JSON `ok=true`，部署与 smoke 的 rc 均为 0；没有接受 SIGABRT/-6。

## 继续推进：同部署指纹 S1 n=5

接入后继续运行 `94_scenario_runner.py --batch S1:5 --policy hybrid
--stage smoke --deployment .../20261006_003632/deployment.json`。
5/5 最终 SUCCEEDED，所有 episode 的路由审计复算通过，安全拒绝为 0。
5 份 episode 属于同一新部署指纹，未与历史校准输入或其他部署混池。

| S1 n=5 路由项             |         实测 |
| ------------------------- | -----------: |
| bootstrap                 |            5 |
| 非 bootstrap 模型决策     |           36 |
| clef 实际调用             |           36 |
| clef 接管                 | 30（83.33%） |
| DeepSeek 接管             |            6 |
| clef measured tokens      |       52,052 |
| 非 bootstrap FSM fallback |            0 |
| harness / routing errors  |        0 / 0 |

快臂被选择的决策耗时 p50 2832.892439 ms、p95 3431.036687 ms；
慢臂被选择的完整 Hybrid 决策耗时 p50 3533.366484 ms。
这些是实际 `perf_counter_ns` 计时，不是纯 GPU 服务耗时或成本估算。
各回合从 A 切换到 B 的 OBSERVE，clef 通常提议低置信度 PICK，
由校准中低 bin 的 0.036223 下界挡住，再升级给慢臂。

第 4 回合保留一次 `OBSERVE_B goal send timeout`：seq=5 的 executor
result 的 outcome/error_code 均为 null，随后慢臂选择再 OBSERVE 并完成任务。
这解释了第 6 次慢臂接管。最终成功不抹去这次管道超时；完整证据在
`episodes/week1_demo_v1_week1_demo_v1-e7ad0742.json`，后续应单独调查
action SendGoal 的稳定性。本轮没有重采覆盖或通过改代码隐藏该异常。

历史 B 抓取 error 23→51 的根因仍为 UNKNOWN；本批次 B 的实际 PICK
均成功，不构成该历史问题已修复的结论。S1 的 n=5 成功也不能解除大批次冻结。
模型同冻结身份重放仍为 NOT_RUN；这里复算的是执行记录的路由身份与结果。

## 可核验产物与操作

`SHA256SUMS.json` 保存冻结文件的原始位置、长度和散列。
`run/` 保留 pilot、extension、合并校准、全部原始推理日志、输入、
profile 激活结果和单对象 reset/client 结果。
`deployment.json` 与 `fleet.log` 保存同一次部署的证据；
`episodes/` 与 `batches/` 保留实际执行记录。

原型审计的浮点精度断言失败和最初未汇总 latency 的草稿均保留。
最终证据为 `run/live_audit_verified.json`；它已核实浮点 `perf_counter_ns`
计时，未将整数截断或者 bootstrap 的耗时写成模型零延迟。

在本机已配置环境下执行冻结证据只读复核：

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/acceptance/school_clef_route_20261006/scripts/verify_frozen.py
```

本轮只增加验收脚本与证据，未修改策略、prompt、全局 timeout 或安装树。
既有构建、304 项测试和 Day-2 验收没有重做。n≥50/400 回合继续冻结。
活动栈保留为已校准的 `hybrid 0.85`；变更保存在 feat 分支，未推送 main。
