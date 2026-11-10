# T05 中转 — n=6 干净批次（6/6 PASS，0 harness 失败）

## 结果

| 指标 | 值 |
| --- | --- |
| 实例 | 6 |
| **Agent 规划正确** | **6/6** |
| **独立验收 PASS** | **6/6 = 100%** |
| harness 失败 | **0** |
| A′ 规则引擎 | **0/6**（全部拒绝） |
| **False Success Rate** | **0/3 = 0.0%**（非空洞） |
| False Failure | 2/5（安全方向） |

## 这一轮修掉的是我自己制造的确定性 bug

### 症状：恰好总是 seed 1004 / 1005 失败
上一轮我把这归因为"Gazebo 不稳定"，重试也没用。**它不是随机的。**

### 根因：我的 domain 公式越界
```
DOMAIN = 220 + (seed % 10) * 3 + attempt

seed 1004 attempt 1 -> 233   ← 超出 ROS 2 domain 上限
seed 1005 attempt 1 -> 236   ← 超出
```

越界 domain 让 `rclpy` 创建节点直接失败：
```
rclpy._rclpy_pybind11.RCLError: error creating node: error not set
```
于是我加的唯一-domain 修复反而**制造了新的失败**。

修正为 `30 + (seed % 10) * 3 + attempt`（范围 31–47），并加边界钳制。
修正后：**6/6 PASS，零 harness 失败**。

### 顺带修的第二层
CycloneDDS 默认参与者索引池太小，而这个 launch 一次起约 12 个节点。
新增 `config/cyclonedds.xml`，把 `MaxAutoParticipantIndex` 提到 120。

## `false_success` 从"空洞的 0"变成真实测量

之前 `false_success` 永远是 0，因为**流水线里没人产生 claim**——
Agent 从不声称成功，所以这个指标**不可能出错，也就不是证据**。

新增 `runtime/verifier/self_assess.py`：把指令、执行计划、**实测最终位置**、
**实际经过的箱子序列**给 Agent，让它自己判断是否完成。然后验收器比对。

### 结果：Agent 自评不可靠

| run | Agent 自评 | 独立验收 | 性质 |
| --- | --- | --- | --- |
| s1000 | 成功 | PASS | 一致 |
| s1001 | **失败** | PASS | **假阴性** |
| s1002 | 成功 | PASS | 一致 |
| s1004 | 成功 | PASS | 一致 |
| s1005 | **失败** | PASS | **假阴性** |

**False Success Rate = 0/3 = 0.0%**（3 次声称成功，全部确实正确）

## 最有价值的发现：Agent 会搞反左右

假阴性的两次，Agent 的措辞是：
> "...inside zone_2 (**the right bin**, radius 0.06) rather than the left bin zone_1"

但 `zone_2` 在 y=+0.05，按 ROS REP-103 **是左侧**。
Agent **在自己的自评里把左右搞反了**，尽管它在**规划时是正确的**。

这说明：
1. 同一个模型在"规划"和"自评"两个任务上表现不同；
2. **绝不能拿 Agent 的自评当验收依据**——它会把成功报成失败；
3. 反过来讲，它也可能把失败报成成功，所以 `false_success` 必须**实测**而不是假设为 0。

## 可以宣称

- T05 中转：Agent **6/6** 规划正确、**6/6** 独立验收通过；
- A′ 规则引擎 **0/6**，区分力稳定；
- False Success Rate **0.0%**，且是**非空洞**测量；
- 该批次 **0 harness 失败**。

## 不能宣称

- **Level 2 整体达成**：只有 T05 一个模板做到 n=6，T01/T02/T04 仍是 n=1；
- **泛化**：全部是 train split，held-out 隔离仍未强制执行；
- **环境已稳定**：只跑了 6 次，之前连续三轮都在修 harness。

## 三轮的教训汇总

| 轮次 | 我误报成 | 实际是 |
| --- | --- | --- |
| 5 | "任务失败" | `$NAMES2` 未定义，观测为空 |
| 6 | "运动学真实问题" | DDS 参与者池耗尽 |
| 7 | "Gazebo 不稳定" | **我自己的 domain 公式越界** |

第三次最严重：**我为了修一个问题而引入了一个新的确定性 bug**，
然后把它归因为外部不稳定。

**规则：任何"环境不稳定"的判断，必须先证明它不是我的脚本造成的。**
