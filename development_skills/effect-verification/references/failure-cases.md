# 失败案例：「命令跑了」当成「命令生效了」（3 次）

## 案例 A —— WSL git 报错，空输出被读成「diff 0 行」

```bash
git -C /mnt/c/.../wt-comp diff --numstat
# fatal: not a git repository: ...
# （stderr，不是 stdout）
```

我看到的 stdout 是空 → 读成「没有差异」→ 据此判断「改动为零」。

**空输出既可能是「没有差异」，也可能是「命令失败」。没看退出码与 stderr 无法区分。**

（背景：WSL 下 `wt-comp` 的 `.git` 是 pointer file，git 必须 Windows 侧跑。）

## 案例 B —— `sed -i` 权限失败，变异没做成

```
sed: couldn't open temporary file benchmark/evaluators/sedBN4Nbh: Permission denied
```

退出码非 0，但我没检查。随后测试「仍然全绿」，
**差一点得出「这些测试不会失败」的错误结论。**

事实是：变异没应用，所以测试当然不变。

改用 Python 写文件后，变异立刻让测试变红。

## 案例 C —— `cd $W` 变量未赋值

```bash
cd $W          # W 未赋值 -> cd 回家目录
python3 -m pytest benchmark/evidence/ -q
# no tests ran in 0.10s
```

**「no tests ran」被我读成「测试通过」。** 实际根本没跑到测试。
改用绝对路径后：**75 passed**。

## 共同点

| 特征                     | A               | B          | C                   |
| ------------------------ | --------------- | ---------- | ------------------- |
| 命令确实执行了           | ✅              | ✅         | ✅                  |
| 效果未发生               | ✅              | ✅         | ✅                  |
| 我根据「没有报错」下结论 | ✅              | ✅         | ✅                  |
| 正确做法                 | 看退出码+stderr | 比文件哈希 | 看有没有 "N passed" |

**结论：效果必须有正向证据。沉默不是成功。**
