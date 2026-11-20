# 发布准备

当前版本 0.1.1，SP 插件 ID `zxaBinbina.sptl`，
Plasma 小部件 ID `org.kde.plasma.sptl`。这些 ID 在后续版本中保持不变。

0.1.1 将 KDE 插件信息与安装包图标更新为项目所有者提供的 `sptl.png`，
任务栏未播放时继续使用原来的 `splayer.svg`。SPlayer 官方插件格式和列表界面
没有自定义图标字段，因此不添加无效的脚本头部字段。
本次通过原生 KPackage 图标路径解析、Plasma 包安装及 QML 布局／封面动画检查。
本机已安装的 PNG 与提供的原图字节一致。

## 当前发布状态

2026-11-20 经项目所有者授权提交，版本为首次公开预览版 0.1.0。

| 平台 | 链接 | 状态 |
| --- | --- | --- |
| GitHub | [v0.1.0 Release](https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/tag/v0.1.0) | 已公开发布预览版，提供插件、两种 Plasma 包、完整源码和 SHA256SUMS |
| SP 插件市场 | [Issue #33](https://github.com/SPlayer-Dev/plugins/issues/33)、[PR #34](https://github.com/SPlayer-Dev/plugins/pull/34) | 官方机器人校验通过，自动创建 PR，等待维护者审核；尚未合并或确认客户端市场可见 |
| KDE Store / Plasma 6 | [2382272](https://store.kde.org/p/2382272/) | 安装包已上传，公开条目可访问，分类为 Plasma 6 Applets |
| KDE Store / Plasma 5 | [2382273](https://store.kde.org/p/2382273/) | 安装包已上传，公开条目可访问，分类为 Plasma 5 Applets；明确标为实验支持，尚未实机验收 |

KDE 条目附中英文安装说明、AGPLv3 许可证、完整源码链接及真实 Plasma 6 任务栏裁剪截图。
两个条目都明确需要 Python 辅助服务和 SP 插件；Plasma 5 条目说明截图来自 Plasma 6。
公开页面和包上传状态已经核实，尚未收到另行的平台人工审核通知。

本次发布前重新执行官方 header 校验、34 项 Python 回归、插件沙箱、QML 布局／动画／控制、
原生 Plasma 6 包和隔离安装／更新／卸载检查，均通过。未完成的实机验收继续按
[验证记录](verification.md) 跟踪，不因市场提交而视为通过。

## 构建材料

源代码包括 SP 插件运行代码、共享设置 schema、Python 辅助程序、
QML 小部件、构建／安装工具、验证脚本和许可证。
运行 `python3 tools/build.py` 生成：

- `dist/zxaBinbina.sptl.js`
- `dist/sptl-plasma5-0.1.1.plasmoid`
- `dist/sptl-plasma6-0.1.1.plasmoid`

辅助程序通过源码仓库和用户级安装脚本交付。
安装包与依赖、缓存、个人配置、日志不纳入 Git。
发布归档需附带 LICENSE、THIRD_PARTY.md 和对应版本的完整源码／构建材料。

## GitHub

仓库为 `zxaBinbina/SplayerPlasmaTaskbarLyrics`，v0.1.0 已发布为公开预览版。
完整实机验收仍按 [验证记录](verification.md) 跟踪，正式稳定版发布前应完成对应验收。
发布版本需同时更新构建脚本、插件头部及 Plasma 包元数据的版本号。

## SP 插件市场

按 [官方流程](https://github.com/SPlayer-Dev/plugins) 提交新建插件 Issue，
提供已生成的 JS 脚本或已公开的脚本直链；本次使用 GitHub Release 的 JS 下载地址。
提交前执行官方 header 校验器，确认 ID 与文件名、版本、API 级别及权限。
公开地址确定后再添加 `@updateUrl`；当前未写入未经发布的下载地址。

分别记录提交时间、机器人校验、维护者审核合并和客户端市场可见状态。
提交材料不等同于审核通过。

## KDE Store

在 Plasma 小部件分类准备条目，说明还需安装辅助服务和 SP 插件。
提供对应 Plasma 主版本的包，附安装说明、许可证、源码链接和真实桌面截图。
当前演示数据的离屏截图只用于开发检查；发布截图应使用已验收的真实任务栏。

分别记录包上传、审核结果及正式上架状态。
