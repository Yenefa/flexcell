# P1.4 stage 2 — T-G1 真实 Gazebo 参数任务（BLOCKED）

## 基础设施（已验证可用）
- `pilot/gazebo_task.py`：`GazeboTaskExecution` 读 `plan.json` 的 `place_pose`，调用真实 `sim_smoke`；
- `gate/acceptance.py`：独立再跑一次真实 Gazebo 并给出 verdict；
- 手工验收：`place_pose=[0.12,-0.15,0.0175]` → `{"passed": true, "status": "PASS", "runtime_fingerprint": "aa5ac497…"}`；
- 失败信号：`place_pose=[0.45,0,0.0175]` → `ROBOT_FAILURE / ERR_SKILL_FAILED / ERR_MOTION_FAILED`。

## Agent 运行结果（3 次尝试，全部失败）
- 模型 deepseek-flash；预算 3 轮；
- 三次都**没有调用 run_execution、也没有写 plan.json**，反复读不存在的 `app.py`/`README.md`（模板里没有这些文件）；
- 结果：`success=false`、`false_success=false`、0 次执行、0 次写文件；记录见 `result.json` / `events.jsonl`。

## 判定
- **BLOCKED（agent 行为问题，不是基础设施问题）**；
- 不在本轮继续第 4 次重试（任务规则：同一问题最多 3 次实质尝试）；
- 下一步（另开任务）：收紧工具 schema/首次动作约束，或改用更强模型；不要修改验收器。
