# 1.1.0 正式版

SP 插件与 Plasma 5／6 小组件版本统一为 **1.1.0**，插件 ID 保持不变。
本次按用户最新指令更新 KDE Store，并提交、推送 GitHub；SP 插件市场投稿保持原状。

## 新增与修正

- 鼠标／触摸板滚轮调节音量，使用 KDE 原生播放器 OSD 显示 SPlayer 名称与实际百分比，0%／100% 处仍有反馈。
- 无法读取 SP 当前配色时，在主题来源选择框下方显示警告，回退 Plasma 配色。
- 方形、圆角方形（1–49%）与圆形封面；圆形可在播放时旋转，暂停冻结；圆角方形不旋转。
- 无当前歌曲时可点击打开 SPlayer 或播放网易云“我喜欢的音乐”；暂停歌曲使用原有点击设置。
- 修复 SPlayer 已运行时无法唤起主窗口的问题；弹窗提供唤起按钮和同步音量滑块。
- 私人 FM 隐藏播放模式，将弹窗及悬停区的上一首改为不喜欢；自动开始播放只使用喜欢歌曲。
- 空闲／加载／停止／断开连接时隐藏悬停控制；四个任务栏操作按钮不显示文字提示。
- 中文设置侧栏显示“设置”，原生关于页的查看许可证按钮显示完整 AGPL 文本。

## 安装与升级

需要 Python 3.10+、systemd 用户会话、gdbus、SPlayer 插件 API 5+，以及
Plasma 5.27／Qt 5.15 或 Plasma 6／Qt 6。KDE Store 单独安装小组件不足以运行，
升级时请同时更新 Python 辅助服务与 SPlayer 插件。

```sh
python3 tools/install.py --reload-plasma
```

在 SPlayer 中导入生成的 `zxaBinbina.sptl.js`，允许 **network、control、api** 权限。
网易云自动播放复用 SPlayer 已登录账号，不需要在 SPTL 输入凭据。
详细说明见 [安装文档](install.md)。

## 发布入口

| 平台 | 链接 | 状态 |
| --- | --- | --- |
| GitHub | [v1.1.0](https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/tag/v1.1.0) | 提供 SP 插件、Plasma 5／6 包、辅助服务源码与 SHA256 校验文件 |
| KDE Store／Plasma 6 | [2382272](https://store.kde.org/p/2382272/) | 1.1.0 已发布，安装包校验值与本地一致 |
| KDE Store／Plasma 5 | [2382273](https://store.kde.org/p/2382273/) | 1.1.0 已发布，安装包校验值与本地一致；Plasma 5 尚未实机验收 |
| SP 插件市场 | [投稿 #33](https://github.com/SPlayer-Dev/plugins/issues/33)、[PR #34](https://github.com/SPlayer-Dev/plugins/pull/34) | 本次未更新投稿，等待维护者审核 |

## 验证与分发材料

48 项 Python 回归、插件沙箱、QML 布局／交互／配置、真实 Qt 图形裁切及双版本包校验，
隔离安装／升级／卸载检查通过。实机小组件滚轮使 SPlayer 音量从 50% 调到 55%，
收到对应原生 OSD 信号后恢复原音量。Plasma 5 包已构建，但仍未在 Plasma 5 桌面实机验收。
完整验证与历史记录见 [验证文档](verification.md)。

`python3 tools/build.py` 生成 SP 脚本及 `sptl-plasma5-1.1.0.plasmoid`、`sptl-plasma6-1.1.0.plasmoid`。
GitHub Release 提供插件、两种小组件安装包、`sptl-source-1.1.0.tar.gz` 与 `SHA256SUMS-1.1.0`。
源码包含辅助服务、共享 schema、插件、小组件、构建／安装脚本、LICENSE 与 THIRD_PARTY.md。
SP 插件的 `@updateUrl` 沿用 GitHub 最新正式版的固定脚本下载地址；历史版本保持可下载。
