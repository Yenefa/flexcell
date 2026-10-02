# FlexCell — 新机器接手清单（2026-10-02，HEAD `4b5db28`）

从零到能跑起来的最短路径。先跑通再谈数据。

## 0. 先确认一件事：能不能 clone

```bash
git clone https://github.com/Yenefa/flexcell.git && cd flexcell
git log --oneline -1        # 应为 4b5db28
```

**不要**从任何旧 WSL clone 继续用（那个还停在 `d03d06c`，落后 11 个提交）。

## 1. WSL 前置（Windows 侧，一次性）

WSL 是**唯一**能跑仿真的地方——Gazebo / ros_gz / MoveIt 在 Windows 上没有原生构建。
Windows 侧只放 git 工作副本和编辑器。

`.wslconfig`（`C:\Users\<你>\.wslconfig`）：

```ini
[wsl2]
memory=10GB
swap=16GB
networkingMode=mirrored
dnsTunneling=true
```

**镜像网络必须开**：校园网会把 NAT 形状的 WSL 流量当成代理，风险是账号被封。
代价是 WSL 里会看到宿主机所有网卡，DDS 可能选错——靠 `setup/104_mainline_env.sh`
里的 Cyclone + 1400B MTU 兜住（见 §4）。

## 2. 建 WSL 工作区

```bash
# WSL 内
sudo useradd -m -s /bin/bash ros 2>/dev/null || true
sudo mkdir -p /etc/wsl.conf.d && printf '[boot]\nsystemd=true\n' | sudo tee /etc/wsl.conf
wsl --shutdown            # 让 systemd 生效
```

然后 `wsl -d Ubuntu-24.04 -u ros` 进来，在**WSL 内** clone（不要从 Windows 侧 copy）：

```bash
cd ~ && git clone https://github.com/Yenefa/flexcell.git agentic_workcell_ws
```

## 3. 装依赖 + 构建 overlay

按 `REPRODUCE.md` 的阶梯走。**注意**：`rosdep` 在这台机器上跑不通（出口 + 证书太弱），
所以依赖正确性靠 build + test 实证兜，不靠 rosdep。**首次构建要装上游 open_manipulator
仓库**，`src/` 是 gitignored 的。

overlay 构建产物不在 Git 里，新机器要自己编：

```bash
cd ~/agentic_workcell_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

新速度约束 servo 还要编 C++ 插件 `flexcell_gazebo`（`libflexcell_carry_dynamics.so`）。

## 4. 起栈

```bash
cd ~/agentic_workcell_ws
source setup/104_mainline_env.sh    # Cyclone + 1400B MTU + ROS_DOMAIN_ID
./setup/flexcell start
./setup/flexcell health
```

**`START OK` + `health ok=true / hard_fail=[]` 才算成功。**

两个已知坑：

- **DDS MTU 依赖具体网络栈。** `setup/cyclone_mtu_safe.xml` 里的 1400 是针对**这台机器**
  测出来的。换机器可能是别的行为。**如果 `start` 卡在"控制器没起来"**，先怀疑这里：
  试更小的值（1200 / 800），或看 `logs/gazebo.log` 有没有 `Ignoring attempt to reload`。
- **不要用 `ros2` CLI 做就绪探测。** 它会被 DDS 分片拖死到超时（E-014）。
  `setup/117_ros_ready.py` 直接调 `ListControllers` 服务，就是为了绕开这个。

## 5. 起栈之后

```bash
./setup/flexcell reset      # 门禁：两个箱子回 canonical、carry disengaged
./setup/flexcell health     # 19 项检查
```

## 6. 需要花钱的只有一件事

LLM 慢路径打 DeepSeek 官方 API。凭据在 `~/.config/flexcell/deepseek_api_key`（mode 600，
**不在 Git 里，新机器要重新配**）。预算账本 `deepseek_budget_20261001.json` 也是本地的，
新机器是**零预算**，需要重新授权并写入限额。

**FSM 臂不花钱。** 想先看数据就跑 `policy=fsm`。

## 7. 第一次真实运行（不跑大样本）

```bash
source setup/104_mainline_env.sh
bash setup/102_mainline_runtime.sh cold fsm      # FSM 臂
```

各脚本用途：`98` 切策略 / `102` 冷启动或切换 / `106` 单物体 / `108` 部署门禁 /
`117` DDS 就绪探测 / `118` 本地模型 / `119` 离线评估与校准 / `120` pose 生命周期 /
`121` carry 新鲜度探针。

**不要一上来跑 `m3_batch_plan.json` 的 400 回合**——它状态是冻结的，前置条件没满足。

## 8. 必读的 4 份文档（按这个顺序）

| 文档                              | 讲什么                                                   |
| --------------------------------- | -------------------------------------------------------- |
| `REPRODUCE.md`                    | 新机 bring-up 的真实坑（含镜像网络、DDS、headless 补丁） |
| `docs/HARDENING_20261002.md`      | **当前状态**：E-016，8 项修复 + Hybrid 4 次全挂          |
| `docs/CARRY_VELOCITY_20261001.md` | 速度约束 servo 的实现边界和失败记录                      |
| `docs/EXPERIMENTS.md`             | E-001..E-016 全部实验结论                                |

`docs/MECHANISM_20261001.md` 是 DDS 根因分析（263 行，抓包级证据），只在查 DDS 时读。

## 9. 当前真实状态（别被过时文档骗）

- **能跑**：FSM 臂双物体全闭环，8 个决策精确重放，误差 2.11 / 14.81 mm
- **不能跑**：Hybrid 在线验收 **4 次全挂**（规划服务不可用 / 客户端超时 / carry
  查询超时 / 官方请求超时）
- **离线重放 FAIL**：同一冻结模型两次跑 10 步只 4 步一致。权重固定 ≠ 输出确定
- **本地 Jev 校准是负面结果**：4/30 匹配 FSM，达不到阈值，Hybrid 主动跳过快路径
- **未完成**：MTC、rosdep 闭包、模型 replay（DeepSeek 侧）、n≥50 基线

## 10. 不要重复踩的坑

- `flexcell reset` 历史上常 **RC=139 段错误但打印 `ok:true`** —— 判据看 JSON，不看退出码
- 栈有残留进程时 `flexcell start` 会 `START REFUSED`。`ros2 launch` 和
  `robot_state_publisher` 是最容易被漏杀的两个
- WSL 重启会清空 `/tmp`（tmpfs），NVM 里没有的临时 CLI 副本要重建
- 镜像网络下 DDS 一定要 LOCALHOST 发现范围 + MTU 限制，否则控制器激活不了
- 长任务必须**分段可续跑**，WSL VM 会重启杀 detached 进程

## 11. 提交规范

- 分支：`feat/` `fix/` `test/` `docs/`，不直接在 main 上开发
- commit：`<type>(<scope>): <summary>`
- **推 main 需要人授权**，agent 不自己 push
- 证据（`setup/acceptance/`）随代码进 Git；凭据、权重、编译产物不进
