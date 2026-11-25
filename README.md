# Splayer Plasma Taskbar Lyrics

简称 **SPTL**。通过 SPlayer Next 官方插件 API、Python 辅助服务和 KDE Plasma 小部件，
显示同步歌词、歌曲封面及播放控制。采用 **AGPL-3.0-only**。

**1.2.1 正式版**：双行原文＋翻译／音译／下一句、单行歌词＋歌曲信息、
逐字高亮与暂停冻结、长文字横向滚动、封面左右切换、自动／固定宽度、
悬停播放控制、滚轮音量、完整歌词与进度跳转、共享设置及中英文显示。
歌词弹窗提供播放模式、收藏和当前播放列表；播放列表支持翻页与点击播放。
悬停区默认增加收藏按钮，可在“交互与离线”设置中关闭“悬停时显示收藏按钮”。
歌词换行和悬停信息带淡入与轻微上移，控制区渐显、宽度平滑伸缩，
封面加载后过渡，按钮提供悬停／按下反馈，完整歌词平滑跟随当前句。
动画速度跟随 KDE 系统设置，也可在小部件配置中关闭“界面动画”。

1.2.1 更新：音量优先通过 MPRIS 原生接口设置，不可用时自动回退插件通道。
滚轮即时显示预计音量；按钮提供即时状态反馈，独立操作并行发送，失败时恢复对应显示。
“交互与离线 → 即时操作反馈”默认开启，关闭后跟随播放器实际状态。
歌词和播放列表切换使用平滑淡入淡出与轻微滑动，动画仍可通过“界面动画”关闭。

封面可选方形、圆角方形或圆形；圆角程度为 1–49%，圆角方形不可旋转。
圆形封面可开启播放时旋转，暂停时冻结。
没有当前歌曲、显示“未在播放”时，点击主体可选择打开 SPlayer，或播放网易云“我喜欢的音乐”。
暂停歌曲时继续使用“点击主体”设置，默认打开完整歌词弹窗。
SPlayer 关闭时会先启动，再在插件连接后开始播放；“SP 关闭时点击”仍可设为无操作。
弹窗提供“打开 SPlayer”按钮和音量滑块，可拖动或用键盘调节，音量与 SPlayer 同步。
自动播放需要在 SPlayer 登录网易云音乐；喜欢歌曲按照原列表顺序插入当前曲目之后，
保留 SPlayer 原有队列。私人 FM 播放时，弹窗隐藏播放模式，弹窗和悬停区的上一首替换为“不喜欢”。
空闲、加载、停止或未连接时，悬停不显示控制按钮；已有歌曲暂停时仍可继续播放。
鼠标／触摸板滚轮调整音量，使用 KDE 原生 OSD 显示 SPlayer 图标、音量百分比和播放器名称。
跟随 SP 无法读取当前主题色时，在主题来源选择框下方显示警告并回退 Plasma 配色。
原生关于页可查看完整许可证；任务栏操作按钮不显示悬浮文字。

## 安装

需要 Python 3.10+、SPlayer Next **插件 API 5+**、Plasma 5.27 / Qt 5.15
或 Plasma 6 / Qt 6，以及 systemd 用户会话。辅助服务只使用 Python 标准库。
主窗口唤起使用 SP 自身的托盘点击，托盘不可用时通过可执行文件或桌面入口唤起已有实例或启动。
1.0 插件使用 API 5 的队列、曲目播放与已登录平台接口。
收藏复用 SP 的 Linux 托盘菜单，需要系统中的 `gdbus` 及 SP 托盘入口。

在项目目录运行：

```sh
python3 tools/install.py
```

小组件和 SPlayer 插件通过各自商店安装，脚本仅安装或更新辅助程序：

1. 右键面板（任务栏），点击「添加或管理小部件」→「获取新小部件」→「下载新 Plasma 小部件」。
   搜索「SPTL」，打开「SPTL 1.2.1 — SPlayer Taskbar Lyrics」条目，点击「安装」。
2. 打开 SPlayer 的「全局设置」→「插件管理」→「插件市场」，找到「SPTL 任务栏歌词」，点击「安装」。
3. 将安装好的「SPTL — SPlayer 任务栏歌词」添加到顶部或底部横向任务栏。
4. **右键 SPTL 小部件 → 配置**，修改后点击“应用”；多个小部件共用同一配置。

组件随任务栏高度自动缩放封面、两行文字和悬停按钮，并保持垂直居中。
字号设置为组件高 42 像素时的基准值；面板变矮时自动缩小文字，避免截断。

首次运行直接安装辅助程序；之后再次运行，会询问升级或卸载。安装完成后提示“卸载请再次运行”。
升级或卸载均保留共享设置和商店安装的组件，升级还会保留自定义播放器路径。
小组件通过 KDE 商店更新，SPlayer 插件通过插件管理更新。更新辅助程序不会重载面板；
若小组件更新后仍使用旧缓存，注销后重新登录。
详情及 AppImage、自定义路径、卸载方法见 [安装说明](docs/install.md)。

## 源码测试版安装

在源码仓库运行：

```sh
./install-from-source.sh
```

脚本提供“仅辅助程序”和“全部组件”选项，也可选择卸载辅助程序。
全量选项从当前工作区构建并安装 KDE 小组件、SPlayer 插件及辅助程序，适合测试尚未发布的修改。
安装全量测试版前需完全退出 SPlayer；安装后启动播放器即可加载测试插件，已有启用状态、权限和设置保留。

```sh
./install-from-source.sh --all --plasma 6
./install-from-source.sh --helper-only
./install-from-source.sh --uninstall
```

Plasma 5 使用 `--plasma 5`；省略时自动检测。自定义 SPlayer 数据目录使用 `--splayer-data`，
例如 `--splayer-data '/path/to/SPlayer-Next/app-data'`。更多选项见 [安装说明](docs/install.md)。

## 构建和验证

```sh
python3 tools/build.py
python3 -m unittest discover -s tests -v
node tests/plugin.mjs
python3 tests/qml_smoke.py
python3 tests/qml_animation_smoke.py
python3 tests/qml_controls_smoke.py
python3 tests/qml_configuration_smoke.py
python3 tests/qml_feedback_smoke.py
python3 tests/package_smoke.py
python3 tests/install_smoke.py
python3 tests/source_install_smoke.py
# 在 KDE Wayland 会话验证真实的圆形裁切（需要图形后端）
python3 tests/qml_cover_render.py --desktop
```

构建输出位于被 Git 忽略的 `dist/`：
独立 SP 插件、Plasma 5/6 各自的小部件目录及 `.plasmoid` 安装包。
QML 验证需要 PySide6 和 Plasma/Kirigami QML 模块，仅为开发检查依赖。

需求依据见 [需求文档](docs/requirements.md)，实现结构与协议见
[架构说明](docs/architecture.md)，验收进展与已知限制见
[验证记录](docs/verification.md)。

## 下载与插件市场

[v1.2.1 正式版](https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/tag/v1.2.1)
提供 SP 插件、Plasma 5/6 安装包、完整源码及 SHA-256 校验值。
插件信息和安装包使用项目所有者提供的图标；任务栏未播放时保留原来的 SPlayer 图标。

- SP 插件市场：已收录「SPTL 任务栏歌词」，在 SPlayer 的插件市场中搜索并安装。
- KDE Store：[Plasma 6](https://store.kde.org/p/2382272/) 和
  [Plasma 5](https://store.kde.org/p/2382273/) 均已上架，也可通过面板的「获取新小部件」入口搜索安装。

从市场安装单个组件后，仍需按上面的安装说明安装辅助服务及另一组件。
发布状态详见 [发布说明](docs/release.md)。
