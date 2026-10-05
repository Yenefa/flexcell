# School agent takeover — FlexCell × home GPU（2026-10-05 晚）

> 给学校笔记本上的 agent：本文是完整接手清单。按序执行，命令可直接跑。
> 家里桌面机（RX 6800）已全部就绪并等你接入；本机（笔记本）是执行主体。

## 0. 六十秒现状

- **主线**：fast arm = Clef-flash Q8_0（本地 GPU 决策模型，typed `/v1/systemone`），
  hybrid τ=0.85/0.03 两个真实 regime 先导已出数；**n≥50 冻结**；B 抓取失败根因 UNKNOWN。
- **main = `d627f9e`**：含全部代码（ClefBackend、per-decision 门禁、-6 修复）+ 证据 + 文档。
- **家里机器**（tailnet `100.87.190.44`）：GPU 推理 API（11435）+ SSH + RDP 全部就绪，
  无人值守加固完成（无更新/无睡眠/无清理任务，服务快照可回滚）。
- **你的主任务**：接通两机 → 跑通跨 WAN smoke → 批次级防静默降级补丁 → τ=0.03 n=20 先导。
- **必读文档**（按序，省一半时间）：`docs/ONBOARDING.md` → `docs/SCHOOL_MODE_20261005.md`
  → `docs/Q8_PILOT_20261005.md` → `docs/Q8_TEARDOWN_20261005.md` → `docs/MODEL_IDENTITY.md`。

## 1. 网络层（先做，其他都依赖它）

```bash
# 1a. Windows 侧装 Tailscale 并登录（家里桌面已在线，机器名 node = 100.87.190.44）
# 1b. 【最高风险实验】Tailscale × WSL2 mirrored 共存测试——两者都改路由/DNS，有已知冲突史，
#     而 mirrored 是校园网硬约束。WSL 内：
curl -s --max-time 8 http://100.87.190.44:11435/health     # 期望 {"status":"ok"}
#     失败退路 ladder：① WSL 保持 NAT 出站（流量经 Windows 栈转发，通常可达）
#     ② Tailscale userspace 模式 ③ 逐项检查 DNS/路由
# 1c. SSH 验收（密码 = 家里 Windows 登录密码；默认 shell 是 cmd，命令按 cmd 语法给）：
ssh fuker@100.87.190.44 "type F:\\flexcell-models\\llama-server.log"   # 或任意探活命令
# 1d. 三通道全通才算过：GPU API 11435 / SSH 22 / RDP 3389（RDP 用客户端连，肉眼验收）
```

**家里断电/重启预案**：家人按电源 → sshd/RDP 随系统起（无需登录）→ 你 RDP 登录一次
= 触发 Startup = `F:\flexcell-models\start-gpu-server.bat` 自动拉起 llama-server。

## 2. FlexCell 侧接线

```bash
# 2a. 代码同步（笔记本 WSL 内；GitHub 拉不动就走代理或 bundle 搬运——踩坑日记有先例）
cd ~/agentic_workcell_ws && git fetch origin && git checkout main && git merge --ff-only origin/main
git log --oneline -1        # 期望 d627f9e
# 2b. 重建（源码变了，必须）
colcon build --symlink-install 2>&1 | tail -3
# 2c. 校准文件：从家里 scp 过来（身份链=模型+权重sha+prompt摘要，端点无关，逐字节拷贝即可）
scp fuker@100.87.190.44:"F:/flexcell-models/../../Users/fuker/.config/flexcell/jev_calibration_clef_q8.json" /tmp/ 2>/dev/null \
  || ssh fuker@100.87.190.44 "type C:\\Users\\fuker\\.config\\flexcell\\jev_calibration_clef_q8.json" > ~/.config/flexcell/jev_calibration_clef_q8.json
#   ↑ 若路径不对，先 ssh 进去 dir 找实际位置；文件 sha256 应与家里一致
# 2d. 快臂 profile：只改端点，其余四个绑定字段照抄（见 docs/MODEL_IDENTITY.md 的表）
#     FLEXCELL_JEV_ENDPOINT=http://100.87.190.44:11435/v1/systemone
#     FLEXCELL_JEV_MODEL=clef-flash-q8_0
#     FLEXCELL_JEV_MODEL_SHA256=8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9
#     FLEXCELL_JEV_CALIBRATION=<上面拷来的文件绝对路径>
# 2e. DeepSeek 凭据（慢臂）：确认 ~/.config/flexcell/deepseek_api_key 存在且 mode 600。
#     笔记本有自己的 ¥1.16/¥5 历史账本——与家里账本不合并，不同指纹不混批。
```

## 3. 第一次验收阶梯（顺序执行，红了停下查，别跳）

```bash
source setup/104_mainline_env.sh
./setup/flexcell start          # START OK + health 19/19 hard_fail=[]
./setup/flexcell reset          # 按 JSON 判，不看退出码
bash setup/102_mainline_runtime.sh cold hybrid 0.85   # 部署门：DEPLOYED policy=hybrid
bash setup/106_single_live.sh /tmp/smoke_crosswan     # 单回合 SUCCEEDED
# 门禁自查：decisions.jsonl 里 jev 提案须有 source=jev、无 fallback、tokens>0、
# 校准 sha == FLEXCELL_JEV_CALIBRATION 文件 sha。跨 WAN 每决策 +10~200ms，对 ~2s 决策无感。
```

## 4. 工作队列（按优先级）

1. **批次级防静默降级补丁（过夜批次前必须）**：批次结束断言 `jev_proposals > 0`
   且校准 sha 匹配，否则 HARNESS_ERROR 非零退出——否则家里断电时 hybrid 静默变
   纯 DeepSeek，30-100× 成本，报告照样绿。
2. **τ=0.03 smoke 5 → n=20 先导**（家里已跑 τ=0.85=14/17、τ=0.03 smoke 3/3；
   注意 τ=0.03 会放行中间箱——历史上 1/5，若成功率掉了那正是实验在测量，保留失败）。
3. τ=0.85 与 0.03 同机同窗对比（成本假设的对照数据）。
4. S4 scenario mapping（#22 还开着）或按 #22 正式宣告出主赛道。
5. S7 分化赛道设计（需预登记的差异化用例 + 独立物理评分 + FSM 对照——单纯位姿扰动
   证明不了"更聪明"，见 Q8_PILOT 的假设声明）。
6. B 抓取失败（23→51）根因追查——两臂共同的物理上限，值得独立 issue。

## 5. 纪律红线

- **n≥50 冻结**；smoke 与 baseline 分母分开；失败全保留，禁止补采覆盖。
- 不同运行指纹/不同校准身份**不并池**（decisions.jsonl 的 policy_trace.calibration sha 是真留痕）。
- 判据看 JSON 不看退出码（RC=139/-6 但 ok:true 是本项目的传统艺能）。
- **禁止接受 -6 为成功**；git 操作：feat 分支开发，推 main 需大统领授权；docs 先 prettier。
- 证据随代码进仓（setup/acceptance/），凭据/权重/编译产物不进。
- 跑完的 episodes 在 `~/.ros/flexcell/episodes/`，批次产物勿留 /tmp 过夜（tmpfs）。

## 6. 家里机器远程操作手册（SSH 到 `100.87.190.44`，默认 shell=cmd）

| 要做什么       | 命令（cmd 语法）                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------------ |
| GPU 服务健康   | `curl http://127.0.0.1:11435/health`（或 tailnet IP）                                                        |
| 重启 GPU 服务  | `F:\flexcell-models\start-gpu-server.bat`（幂等，先杀后起）                                                  |
| 看 GPU 日志    | `type F:\flexcell-models\llama-server.log`（或 PowerShell `Get-Content -Tail 50`）                           |
| 看 GUI/弹窗    | RDP 连 `100.87.190.44`（登录即触发 Startup，断电重启后的全链复活入口）                                       |
| 这周被禁的服务 | 别手动开——快照在 `F:\flexcell-models\service-snapshot.json`，回滚跑 `unattended-week-rollback.ps1`（管理员） |
| 已知状态       | 无 Windows Update（已三重封死）、无睡眠（固件不支持 S1/S2）、无自动清理任务                                  |

## 7. 已知坑速查（全部本项目实测，详见踩坑日记）

- 笔记本 mirrored × Tailscale 冲突 → §1b 的 ladder。
- WSL 重启杀 detached 进程 → 长任务分段可续跑，产物勿留 /tmp。
- `TaskStop` 杀 wsl.exe 会连坐杀栈。
- gh/GitHub 网络抖 → 代理 7890 或 bundle 搬运（家里有先例脚本）。
- 校准身份五字段必须与 profile 逐字段一致，否则静默旁路快臂（silently 100% escalate）。
- `118_local_models.py start fast` 不会覆盖你的 clef profile（会写 side 文件并告警）——
  但**别跑它**，跑之前想清楚。

> 交接人：家里的 desktop 会话（2026-10-05）。问题先查本文 + 五份必读文档 + 踩坑日记
> （`大局复利踩坑日记.md` / `踩坑日记/开发踩坑.md` 的 flexcell 条目）。
