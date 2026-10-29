# Joint 跟随窗口：启动失败记录

`startup_629e496/` 是提交 `629e49679ccef5484e030506b3c0ee3dc175e0a5` 的第一次
A/B 窗口原始文件。窗口 ID 为 `6ca0ee15b85243c98b39fdb11e9e271f`，状态永久保留
为 **STOPPED**。首轮 strict health 超时；Gazebo 日志显示 Ogre 渲染插件加载失败
并发生段错误。未派发任何任务，未运行 B，没有物理跟随观测，不计为抓取成败。

运行前源码与安装一致，但本地精简镜像删去了 `/usr/share`；包数据库仍声称安装了
Mesa，实际缺少 `/usr/share/glvnd/egl_vendor.d/50_mesa.json`。从已有开发容器恢复
该文件后，独立 EGL 探针可创建 OpenGL 4.5 llvmpipe 上下文。恢复文件 SHA256：
`cd3881df4227c13ca7f9cfe6c78820f21d5f7a00a41b299214f6f827e63be369`。
这是本地容器环境修复；官方 Dockerfile 的正常包安装不应删掉这些运行时数据。

`egl_negative/` 是**后续受控负例**：设置
`__EGL_VENDOR_LIBRARY_FILENAMES=/nonexistent/flexcell-negative.json`，隐藏厂商
描述后，新预检拒收。`egl_positive/` 是恢复环境后的无显示渲染探针。两者都没有
启动 Gazebo、机器人或任务；负例不能冒充原始故障日志。Mesa 的全平台探针会因
无 X11/Wayland 返回 3，所需 surfaceless 平台的实际 OpenGL 上下文独立判定。

原始文件逐字复制，摘要在 `inputs.json`。离线校验：

```sh
python3 setup/acceptance/joint_follow_20261029/verify_startup.py
```

修复后的窗口另见 `infra/joint-follow-window-after-egl.json`。它保留前序失败的 ID
和结果摘要，使用独立输出目录；A/B 任务数和物理/相机门槛不变。任何新结果均不得
覆盖这里的失败，D3 默认准入仍是 NO_GO。

## 第二个窗口：控制器启动超时

`startup_95e8007/` 是提交 `95e80075dbd182a2c33ce8975b7810f942403345` 的独立
后续窗口，ID 为 `846db7d03ffb44d584a8b9dfdc02e1a1`。EGL 预检和 Gazebo 渲染启动
已通过，但相机初始化期间 `joint_state_broadcaster` 的激活请求超过默认 5 秒；
之后 arm/gripper 已激活，broadcaster 仍未激活，strict health 拒收。此窗口仍为
**STOPPED，0 次任务派发**，未运行 B，不能作为跟随验证或抓取样本。

该轮的全部原始文件保留；逐 2 ms 轨迹做了无损 gzip 压缩，解压后的 SHA256、字节数
与 9,764 行记录由 `startup_95e8007_inputs.json` 固定，原始未压缩文件仍留在运行目录。
启动期包含 DetachableJoint 的短暂初始组件，不能把它拼成主动抓取证据。终止仿真栈时
MoveIt 进程也记录了退出段错误，原始日志未裁掉。

修复将控制器**启动切换应答**的等待上限设为 30 秒，任一模型创建或 broadcaster
前置步骤失败则阻断后续启动；任务运动超时、抓取容差及失败码不变。身份校验新增
源码与实际安装的 launch 文件比对。新独立预声明为
`infra/joint-follow-window-after-startup.json`，同时关联前两份 STOPPED 记录，A/B 顺序
与物理/相机质量门槛不变。
