# 消除缺陷的**类别**，不是个案：4 个运行器合并为 1 个

## 连续两轮栽在同一类缺陷上

| 轮次 | 后果 |
| --- | --- |
| 上上轮 | 自评没跑 → 声明全缺 → false success 空洞 |
| 上轮 | **恢复没跑 → R 臂不存在** |

两次都是：运行器 `cd` 到仿真目录后，用**相对路径**调项目脚本。

**根因不是某一行路径，而是 4 个近重复的运行器**——
每次新建一个，就把旧 bug 复制一遍：

| 文件 | 行数 | 相对路径调用 |
| --- | --- | --- |
| `evobot_pair16.sh` | 91 | 2 |
| `evobot_pair32.sh` | 91 | 2 |
| `evobot_pair48.sh` | 113 | 3 |
| `evobot_rerun3.sh` | 90 | 2 |

## 修复：一个运行器，全程绝对路径

`run_batch.sh`：**所有 helper 在开头声明为 `$W/...` 绝对路径**，
并在启动前逐个 `-f` 检查存在性。
运行器内部的 `cd` 因此**不可能**再影响任何脚本调用。

```bash
PLAN_B="$W/runtime/planner/prepare_baseline_b.py"
RECOVERY="$W/runtime/recovery/recovery_driver.py"
ASSESS="$W/runtime/verifier/self_assess.py"
...
for f in ...; do [ -f "$f" ] || { echo "FATAL: missing helper $f"; exit 3; }; done
```

另加：恢复步骤若**没产出决策文件**，立即报错并标注阶段，
不再静默地让「R 臂」退化成 B 臂。

## 用测试禁止这个类别回归

`benchmark/tests/test_runner_hygiene.py`：

| 测试 | 内容 |
| --- | --- |
| 无相对路径调用 | 扫描**在用**运行器，任何裸 `python3 runtime/...` 即失败 |
| helper 必须绝对声明 | 逐个正则检查 `NAME="$W/...` |
| 必须内置校验 | `validate_batch.py`、`BATCH_REJECTED`、`RECOVERY_DID_NOT_RUN` 存在 |
| **旧运行器必须保留缺陷** | 它们是「实际跑了什么」的证据，**改掉就是篡改记录** |

最后一条很重要：我把 4 个旧脚本标注 `SUPERSEDED` 但**保留了其中的相对路径调用**，
测试断言它们仍在——这样缺陷本身也是可审计的。

## 冒烟测试抓到一个我自己新引入的缺陷

运行器写完、语法检查通过，第一次真跑却**在规划后静默退出**。

原因：我给运行器加了 `set -u`，而 **ROS 的 setup.bash 不兼容它**：

```
/opt/ros/jazzy/setup.bash: line 8: AMENT_TRACE_SETUP_FILES: unbound variable
```

source 失败 → 函数中止 → 阶段文件为空。
**如果没有先跑 1 例冒烟，我会在 25 分钟的批次跑完后才发现。**

已改为 `set -o pipefail`。

## 冒烟结果（1 例端到端）

```
--- attempt 1 (arm B) ---
--- recovery (arm R) ---
--- final state ---
--- self-assessment (claim) ---
  agent claims success=true
--- grade WITH the claim ---
  passed= True claimed= True false_success= False

=== BATCH VALIDATION ===
NOTE: no first attempt failed, so the recovery path was never exercised.
      This batch supports NO claim about arm R.
Batch structure OK
```

**每一步都真的执行了**，且校验器正确指出「本批无失败，不能对 R 作声明」。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **194 passed** |
| 封存 | `BLOCKED_GOOD` |
| 验收器 | **未改** |
| 冒烟 | **1 例端到端通过** |

## 不宣称

- 不宣称运行器无其他缺陷（已两次被证明不是）；
- 不宣称 B/R 指标已可报（需要**有失败**的批次来测恢复）；
- 旧运行器的结果仍按上轮撤回归档；
- **未上真机，M0**。
