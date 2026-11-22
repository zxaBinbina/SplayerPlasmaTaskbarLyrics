# 1.0 正式版

版本 **1.0.1**，SP 插件 ID `zxaBinbina.sptl`，Plasma 小部件 ID `org.kde.plasma.sptl`。
插件 ID 保持不变，Plasma 5 和 6 使用同一版本号、各自的安装包。

## 新增功能

- 方形／圆形封面，圆形可开启播放时旋转，暂停冻结。
- 未播放时点击主体可选择打开 SPlayer，或播放网易云“我喜欢的音乐”；关闭时先启动。
- 弹窗增加“打开 SPlayer”按钮和与播放器同步的音量滑块，支持鼠标和键盘。
- 用户取消私人 FM 功能，自动播放仅保留喜欢的音乐，播放模式按钮保持原功能。

## 更新要求

需要 SPlayer 插件 API 5、Python 3.10+、systemd 用户会话，以及 Plasma 5.27／Qt 5.15 或 Plasma 6／Qt 6。
重新运行安装脚本并重新导入 SP 插件，允许 **network、control、api** 权限。
自动播放复用 SPlayer 已登录的网易云账号，不在 SPTL 输入账号或凭据。
喜欢歌曲依原顺序加入当前曲目之后，保留播放器已有队列；不修改 SP 程序或私有数据库。

```sh
python3 tools/install.py --reload-plasma
```

Plasma 会短暂重载，应用窗口保留。也可不传 `--reload-plasma`，更新后注销再登录。
详细说明见 [安装文档](install.md)。

## 发布入口

| 平台 | 链接 | 状态 |
| --- | --- | --- |
| GitHub | [v1.0.1](https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/tag/v1.0.1) | 1.0 正式版，提供 SP 插件、两种 Plasma 包、完整源码与 SHA256SUMS-1.0.1 |
| SP 插件市场 | [投稿 #33](https://github.com/SPlayer-Dev/plugins/issues/33)、[PR #34](https://github.com/SPlayer-Dev/plugins/pull/34) | 1.0 脚本已通过机器人校验，PR 尚未合并，等待维护者审核 |
| KDE Store／Plasma 6 | [2382272](https://store.kde.org/p/2382272/) | 按用户要求暂不更新，保留 0.1.1 |
| KDE Store／Plasma 5 | [2382273](https://store.kde.org/p/2382273/) | 按用户要求暂不更新，保留 0.1.1；Plasma 5 尚未实机验收 |

KDE Store 单个包仍需要安装 Python 辅助服务和 SP 插件。
1.0.1 修复从旋转圆形封面切回方形时残留旋转角度的问题。1.0.0 与历史预览版 0.1.0、0.1.1 保留在 GitHub Release，两个市场条目沿用原 ID。

## 验证与构建材料

官方插件头校验、39 项 Python 回归、插件沙箱、QML 布局／动画／控制交互、
真实 Qt 图形渲染的圆形／方形裁切，以及 Plasma 5／6 包和隔离安装／更新／卸载检查通过。
私人账号下的实际网易云播放和 Plasma 5 桌面验收未完成，模拟接口检查不作为实机验收。
验证范围与历史记录见 [验证文档](verification.md)。

`python3 tools/build.py` 生成：

- `dist/zxaBinbina.sptl.js`
- `dist/sptl-plasma5-1.0.1.plasmoid`
- `dist/sptl-plasma6-1.0.1.plasmoid`

辅助服务通过 `sptl-source-1.0.1.tar.gz` 中的源码和安装脚本交付。
归档包括 LICENSE、THIRD_PARTY.md、共享 schema、插件、小部件和构建／安装材料。
SP 插件头部的 `@updateUrl` 指向 GitHub 最新正式版的固定脚本下载地址。
安装包、依赖、个人配置、浏览器会话和日志不纳入 Git。
