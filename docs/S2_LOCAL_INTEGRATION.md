# 本地 S2 Gazebo 联调交付

这里的 S2 指本地仿真电脑，不是真实 OpenMANIPULATOR-X。此 PR 交付测试准备，
**尚未在 S2 执行**；默认后端、物理门限、D3 NO_GO 和 n≥50 冻结均保持。
依赖 #78、#81、#85，基于 `fix/native-audit-lifetime`；不需要先合入整个 PR 堆叠链。

接续候选使用 [PR #92](https://github.com/Yenefa/flexcell/pull/92) 的
`fix/archive-binding-status`，包含释放尾段修复、脱开观察超时拒收及 100 ms 在线采样窗口。
在线 50 Hz 采样仍不替代离线 500 Hz 原始 hold 检查；原 1.5 mrad 限制不变。
下列命令已指向这个候选；此处不宣称新增 S2 或有画面窗口已通过。

测试严格串行，共两项逻辑任务，无恢复和替换样本：

| 顺序 | 新声明 | 本地验收 |
| --- | --- | --- |
| 1 | `infra/s2-joint-camera.json` | 一次 A 正常 Joint/MTC 抓放；沿用 #81 完整预定位、≥10 sim s 跟随、2 ms 原始步、接触/释放和规划快照门；新增同轮 RGB |
| 2 | `infra/s2-false-attach-camera.json` | 一次 #78 guard 输入故障：30 mm world-x、10 帧 / 0.2 s；类型化失败、取消和确认终端、无 PLACE；同轮 RGB 必须覆盖注入区间 |

固定关节没有物理打滑。故障只改变 **guard 输入上报的 pose**，不改变原始 2 ms 物理记录或
相机里的箱子位置；画面用于看实际运动和停机响应。Observe 仍是 ground truth，RGB 是数据采集。
正常窗口失败时，第二项保持 NOT_RUN，不跳过第一项单独补跑第二项。

## 构建与准备

在 S2 的 Ubuntu/WSL2 shell 使用一个干净工作树。完整 ref 避免同名 tag 歧义：

```bash
git fetch origin refs/heads/fix/archive-binding-status:refs/remotes/origin/fix/archive-binding-status
git worktree add --detach ../flexcell-s2 refs/remotes/origin/fix/archive-binding-status
cd ../flexcell-s2
s2_revision=$(git rev-parse HEAD)
s2_image="flexcell-s2:$s2_revision"
docker build -f infra/Dockerfile.sim --build-arg "SOURCE_REV=$s2_revision" -t "$s2_image" .
mkdir -p "$HOME/flexcell-artifacts"
s2_window="s2-$(date -u +%Y%m%dT%H%M%SZ)"
docker run --init --rm -v "$HOME/flexcell-artifacts:/artifacts" "$s2_image" \
  python3 /opt/flexcell/repo/scripts/s2_local.py --out "/artifacts/$s2_window"
```

最后一条只生成 `plan.json`、实际源码/import/install 身份和两份冻结声明，状态必须是
`PREPARED_NOT_RUN`，不启动 Gazebo 或动作。镜像按候选源码独立构建，不 source 本机旧部署
`~/.local/share/flexcell/.../install`。实际导入包的文件字节必须与镜像源码相同，之后每个
原有 smoke 还会核对运行身份、映射的 native 库、world/config SHA、相机 EGL 和启动健康。
软件渲染是现有镜像默认设置；不要求改本机 GPU 驱动。

首次完整镜像构建**估计 30–90 分钟**，命中依赖缓存约 **5–15 分钟**；这是排期估算，
不是 S2 实测。保留 Docker 镜像与完整两轮 RGB/rosbag/原始步，建议构建前可用空间至少
20 GB。构建或准备失败时还没有派发任务，应先保留对应日志排查。

## 只执行一次

在同一个 shell 继续（沿用上面的三个 `s2_*` 变量）：

```bash
docker run --init --rm -v "$HOME/flexcell-artifacts:/artifacts" "$s2_image" \
  python3 /opt/flexcell/repo/scripts/s2_local.py --out "/artifacts/$s2_window" --execute
```

执行前再次比对准备时的源码/import/install/native 身份和声明字节。已有 `attempt.json`
即拒绝再次执行；失败或中断不自动续跑。任一原有门禁失败、未知终端、缺少同轮画面或坏记录，
整个交付为 STOPPED，后续项 NOT_RUN。保留原始退出码和日志；不改 #88 已暴露的
20 ms 释放尾部或 1.5 mrad hold 限制来换绿。中断/容器被终止的记录可能停在 RUNNING 或
INCOMPLETE，均不算通过；应连同 owned-process、stack 和终端日志复核，不重用该窗口。

镜像已构建时，两个窗口**估计约 5–15 分钟**；软件渲染负载可能更慢。现有每项
window 的 trial 最长等待 900 s，另有受控清理等待，故障时不承诺这个估算。
本准备 PR 不在云端再执行这两项物理任务。

## 需要带回的文件

整个 `$HOME/flexcell-artifacts/$s2_window/` 原样保留，包括失败项：

- `plan.json`、`identity.json`、`declarations/`、`attempt.json`、`report.json`；
- 两份 window、各自 trial 的 result、task/skill/carry、world/params、运行身份、
  strict health/reset、planner CDR、2 ms physics/contact、RGB PNG、frames/collection 和原始 rosbag；
- `normal.log` / `false_attach.log`，以及通过时导出的两张 `*-preview.png`。

`LOCAL_INTEGRATION_PASS` 仅表示这两个固定窗口及其现有门禁/对齐 RGB 检查通过；
`declared_host_role=S2` 是操作者声明，程序不自动验证机器身份。人工还需看正常抓放和
注入时的画面、核对日志与同一注入时刻。没有接触抓取、感知策略、实机、成功率或 D3 GO 声明。

离线检查无需启动仿真：

```bash
python3 -m pytest -q src/flexcell/flexcell_skills/test/test_s2_local.py
```
