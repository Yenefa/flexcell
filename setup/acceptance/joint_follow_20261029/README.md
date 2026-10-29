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
