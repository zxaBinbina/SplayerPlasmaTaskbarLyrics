# Splayer Plasma Taskbar Lyrics

简称 **SPTL**。通过 SPlayer Next 官方插件 API、Python 辅助服务和 KDE Plasma 小部件，
显示同步歌词、歌曲封面及播放控制。采用 **AGPL-3.0-only**。

已实现第一版原型：双行原文＋翻译／音译／下一句、单行歌词＋歌曲信息、
逐字高亮与暂停冻结、长文字横向滚动、封面左右切换、自动／固定宽度、
悬停播放控制、滚轮音量、完整歌词与进度跳转、共享设置及中英文显示。
歌词弹窗提供播放模式、收藏和当前播放列表；播放列表支持翻页与点击播放。
悬停区默认增加收藏按钮，可在“交互与离线”设置中关闭“悬停时显示收藏按钮”。
歌词换行和悬停信息带淡入与轻微上移，控制区渐显、宽度平滑伸缩，
封面加载后过渡，按钮提供悬停／按下反馈，完整歌词平滑跟随当前句。
动画速度跟随 KDE 系统设置，也可在小部件配置中关闭“界面动画”。

## 安装

需要 Python 3.10+、SPlayer Next **插件 API 4+**、Plasma 5.27 / Qt 5.15
或 Plasma 6 / Qt 6，以及 systemd 用户会话。辅助服务只使用 Python 标准库。
主窗口唤起优先使用 SP 的 MPRIS，启动优先使用已安装的可执行文件或桌面入口。
播放列表需要 SP 插件 API 5 的队列接口；旧版仍可使用其他功能。
收藏复用 SP 的 Linux 托盘菜单，需要系统中的 `gdbus` 及 SP 托盘入口。

在项目目录运行：

```sh
python3 tools/install.py
```

然后：

1. 在 SP 的「设置 → 插件管理 → 本地导入」中导入
   `~/.local/share/sptl/zxaBinbina.sptl.js`（遵循 `XDG_DATA_HOME`）。
2. 启用插件并允许 **network、control** 权限。
3. 在顶部或底部横向任务栏添加「SPTL — SPlayer 任务栏歌词」。
4. **右键 SPTL 小部件 → 配置**，修改后点击“应用”；多个小部件共用同一配置。

组件随任务栏高度自动缩放封面、两行文字和悬停按钮，并保持垂直居中。
字号设置为组件高 42 像素时的基准值；面板变矮时自动缩小文字，避免截断。

安装脚本支持更新，更新后重新导入插件。Plasma 可能缓存旧小部件代码，
移除后重新添加也可能继续使用旧版本。更新现有小部件时可运行
`python3 tools/install.py --reload-plasma`，面板会短暂重载，应用窗口保留；
也可以更新后注销再登录。
详情及 AppImage、自定义路径、卸载方法见 [安装说明](docs/install.md)。

## 构建和验证

```sh
python3 tools/build.py
python3 -m unittest discover -s tests -v
node tests/plugin.mjs
python3 tests/qml_smoke.py
python3 tests/qml_animation_smoke.py
python3 tests/qml_controls_smoke.py
python3 tests/package_smoke.py
python3 tests/install_smoke.py
```

构建输出位于被 Git 忽略的 `dist/`：
独立 SP 插件、Plasma 5/6 各自的小部件目录及 `.plasmoid` 安装包。
QML 验证需要 PySide6 和 Plasma/Kirigami QML 模块，仅为开发检查依赖。

需求依据见 [需求文档](docs/requirements.md)，实现结构与协议见
[架构说明](docs/architecture.md)，验收进展与已知限制见
[验证记录](docs/verification.md)。

## 下载与插件市场

[v0.1.0 公开预览版](https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/tag/v0.1.0)
提供 SP 插件、Plasma 5/6 安装包、完整源码及 SHA-256 校验值。

- SP 插件市场：[投稿 #33](https://github.com/SPlayer-Dev/plugins/issues/33) 已通过机器人校验，
  [PR #34](https://github.com/SPlayer-Dev/plugins/pull/34) 等待维护者审核，尚未正式收录。
- KDE Store：[Plasma 6](https://store.kde.org/p/2382272/) 和
  [Plasma 5](https://store.kde.org/p/2382273/) 条目已上传，公开页面可访问。
  Plasma 5 包仍属实验支持，尚未实机验收。

从市场安装单个组件后，仍需按上面的安装说明安装辅助服务及另一组件。
发布状态详见 [发布说明](docs/release.md)。
