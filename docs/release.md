# 1.2.1 正式版

SP 插件与 Plasma 5／6 小组件版本统一为 **1.2.1**，插件 ID 保持不变。

## 新增与修正

- 音量优先使用 SPlayer 的 MPRIS 原生接口，接口不可用或操作失败时自动回退现有插件通道。
- 每次滚轮输入立即发送绝对音量设置，OSD 显示预计的新百分比、SPlayer 名称和原版图标。
- 播放／暂停、收藏、模式、定位和选曲提供即时反馈；发送或执行失败时恢复对应显示，旧失败不覆盖新操作。
- 新增“交互与离线 → 即时操作反馈”，默认开启；关闭后跟随播放器实际状态，请求仍即时发送和并行处理。
- 播放控制、曲目操作、模式、音量和队列读取分别执行，慢请求不再阻塞独立按钮操作，同类操作保留必要顺序。
- 弹窗歌词和播放列表切换增加淡入淡出与轻微横向滑动；支持快速折返，关闭弹窗或关闭动画时立即结束。
- 滚轮支持鼠标、触摸板及系统合成事件，0%／100% 处仍有反馈。
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

| 平台 | 链接 | 分发内容 |
| --- | --- | --- |
| GitHub | [v1.2.1](https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/tag/v1.2.1) | SP 插件、Plasma 5／6 包、辅助服务源码与 SHA256 校验文件 |
| KDE Store／Plasma 6 | [2382272](https://store.kde.org/p/2382272/) | 1.2.1 Plasma 6 安装包 |
| KDE Store／Plasma 5 | [2382273](https://store.kde.org/p/2382273/) | 1.2.1 Plasma 5.27+ 安装包 |
| SP 插件市场 | [投稿 #33](https://github.com/SPlayer-Dev/plugins/issues/33)、[PR #34](https://github.com/SPlayer-Dev/plugins/pull/34) | 插件投稿，维护者审核后收录 |

后续仅小组件或辅助服务有改动时，不更新 SPlayer 投稿 issue；插件实现有改动时才同步投稿。

## 验证与分发材料

Python 回归、插件沙箱、QML 布局／交互／配置／动画／即时反馈、图形裁切、双版本包校验，
以及隔离安装／升级／卸载检查通过。
完整验证与历史记录见 [验证文档](verification.md)。

`python3 tools/build.py` 生成 SP 脚本及 `sptl-plasma5-1.2.1.plasmoid`、`sptl-plasma6-1.2.1.plasmoid`。
GitHub Release 提供插件、两种小组件安装包、`sptl-source-1.2.1.tar.gz` 与 `SHA256SUMS-1.2.1`。
源码包含辅助服务、共享 schema、插件、小组件、构建／安装脚本、LICENSE 与 THIRD_PARTY.md。
SP 插件的 `@updateUrl` 沿用 GitHub 最新正式版的固定脚本下载地址；历史版本保持可下载。
