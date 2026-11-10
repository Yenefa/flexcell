# Held-out 隔离：从「写了规格」变成「强制生效」

之前每一轮我都标注「held-out 隔离是规格，未强制执行，故不得报告泛化」。
这一轮把它变成了**可验证的 OS 级隔离**。

## 环境能力探测（先问能做什么，不假设）

| 机制 | 结果 |
| --- | --- |
| `unshare -m` 挂载命名空间 | Operation not permitted |
| `bwrap` / `firejail` | 未安装 |
| `sudo -n` | 可用 |
| 非特权 `setpriv` 降权 | 不允许（setresuid 失败） |
| **`sudo -n setpriv --reuid=1001`** | **可行** |

验证：uid 1001 下 `root:root 600` 文件 `PermissionError`，且 `sudo -n true` 被拒。

## 设计：把答案拆出去

| 侧 | 路径 | 内容 | Agent 可读 |
| --- | --- | --- | --- |
| 公开 | `benchmark/held_out/public/HO-*.json` | instruction / objects / zones / 不透明 id / budget | **是** |
| 封存 | `/etc/evobot/sealed/HO-*.json`（root:root 600，目录 700） | expected_goal / constraints / template / seed | **否** |

公开文件**不含** `expected_goal`、`constraints`、`template_id`、`random_seed`、
`instance_sha256`；task_id 改为加盐哈希 `HO-<12hex>`，不泄露 seed 与模板。
36 个公开任务 + 36 个封存答案。

## 双侧验证

```
=== agent side (uid 1001, no sudo) ===
SEALED_READ_BLOCKED
PUBLIC_READ_OK
public keys: evaluator_version, execution_budget, instruction,
             objects, split, task_id, zones
has expected_goal: False

=== evaluator side (privileged) ===
sealed answers: 36
reconstructed: T02_exclusion / HO-008a467cde3f
independent verdict: passed=true
```

端到端：Agent 侧调用 `sealed_evaluate.py` 得 `PermissionError`；
特权侧重建 spec 并使用**同一个 `evaluate.py`** 判分——
**没有复制或削弱任何验收逻辑**。

## 补上的两个漏洞

### 1. 工作区里还有 36 份明文答案
`benchmark/held_out/held_out/*.json` 含 `expected_goal`。它们**从未进入 git**
（`git ls-files` = 0，无历史记录），所以历史没被污染；但 Agent 进程能读到。已移除。
**这不是删除失败证据**，是移除答案密钥。

### 2. `build_sets.py` 重跑会重新生成它们
改成：未设置 `EVOBOT_HELD_OUT_STAGING` 时**跳过 held-out 生成**并打印说明。
验证：裸重跑后明文文件数仍为 0，公开任务仍在。
**隔离必须防得住「下次重跑」，否则等于没有。**

## 我的守卫缺陷（测试抓到）

第一版 `assert_public_is_clean` 扫整个 JSON 文本找禁用词，把指令里自然出现的
「in this order」判成泄露 `order`。改为**只检查结构键**——答案字段是结构性的，
自然语言里说「order」完全合法。

## 限制（必须说明）

1. **这是 OS 权限隔离，不是内核命名空间**。以 root 启动的 Agent、或能提权的进程，
   可以突破。Agent 必须在 uid 1001 下运行。
2. 公开任务仍可被**推理**出答案——那是任务本意。封存的是**判分标准**。

## 影响

- **现在可以跑 held-out 并报告泛化**，前提是 Agent 确实在隔离 UID 下运行；
- 本轮**尚未**跑 held-out 执行，所以**仍不报告任何泛化数字**；
- 旧 v0.1 held-out 集视为**已退役**，新加盐 ID 与封存答案从未进入 checkout。

## 测试

**58 个离线测试**通过（新增 6 个封存契约测试）。
