# 用户级安装与维护

## 常规安装

执行 `python3 tools/install.py`，无需 sudo。脚本只安装或更新辅助程序、共享设置定义与许可证，
并启用或重启 `sptl-bridge.service` 用户服务，不构建或安装小组件及 SPlayer 插件。
首次运行直接安装；检测到已有辅助程序时，再次运行会提供「升级 / 卸载 / 取消」菜单。
安装完成后提示“卸载请再次运行此脚本，并选择「卸载」”。无交互终端时使用 `--upgrade` 或 `--uninstall` 明确选择操作。

KDE 小组件获取方式：右键面板（任务栏）→「添加或管理小部件」→「获取新小部件」→「下载新 Plasma 小部件」。
输入「SPTL」搜索，进入「SPTL 1.2.1 — SPlayer Taskbar Lyrics」条目，点击「安装」。
SPlayer 插件获取方式：「全局设置」→「插件管理」→「插件市场」→「SPTL 任务栏歌词」→「安装」。
需要 SPlayer 插件 API 5+；插件的权限及更新通过官方插件管理处理。

右键小部件配置“封面形状”“播放时旋转圆形封面”和「显示“未在播放”时点击」。
圆角方形可设 1–49% 的圆角程度，不可旋转。
自动播放“我喜欢的音乐”需要在 SPlayer 中登录网易云音乐；不需要在 SPTL 中输入账号或凭据。
空闲点击设置仅在没有当前歌曲、显示“未在播放”时生效；暂停时使用“点击主体”设置，默认打开歌词弹窗。

辅助程序安装只需要 Python 和可用的 systemd 用户会话，无需检测 Plasma 版本或提供 kpackagetool。
从桌面外启动的终端会尝试当前用户的 `/run/user/<uid>/bus`；若没有可用用户会话，写入安装文件前会明确提示。
旧 `--plasma` 与 `--reload-plasma` 参数仅兼容旧命令，不再安装小组件或重载面板。

## AppImage 或自定义数据目录

```sh
python3 tools/install.py \
  --splayer-command '/path/to/SPlayer-Next.AppImage' \
  --splayer-config '/path/to/SPlayer-Next/app-data/config/settings.json'
```

服务配置中的这些参数用于程序定位，不属于第二套外观设置。
标准安装会尝试 XDG_CONFIG_HOME 下的 SPlayer-Next、splayer-next、splayer_next
以及 Flatpak 配置目录。SP 封面缓存位置跟随它的 `cache.dir`。

## 源码测试版安装

仓库根目录的 [install-from-source.sh](../install-from-source.sh) 可从任意当前目录调用，
使用该脚本所在工作区的源码，不下载 GitHub 发行包。

```sh
./install-from-source.sh
```

菜单提供仅辅助程序、全部组件、卸载辅助程序及取消。
全量安装前请完全退出 SPlayer，脚本会在写入文件前检查播放器进程及安装环境。
全量选项构建当前源码，使用对应的 `kpackagetool` 安装或更新同 ID 的 KDE 小组件，
将 SPlayer 测试插件登记到 `app-data/plugins/manifest.json` 并写入 `plugins/scripts/`。
登记格式为已验证的 SPlayer 插件清单版本 1；其他插件、用户权限、启用状态和插件设置均保留。
启动 SPlayer 后加载新脚本；若该插件原先被禁用，请在插件管理中启用。

```sh
./install-from-source.sh --all --plasma 6
./install-from-source.sh --all --plasma 5
./install-from-source.sh --helper-only
./install-from-source.sh --uninstall
./install-from-source.sh --help
```

未指定 `--plasma` 时根据桌面会话或 `plasmashell --version` 自动检测。
自定义播放器路径使用 `--splayer-command`；自定义配置使用 `--splayer-config`，
或通过 `--splayer-data` 指定包含 `config/` 与 `plugins/` 的 `app-data` 目录。
更新保留辅助程序的共享设置及已保存的播放器路径。
只有显式使用 `--reload-plasma` 才会在全量安装后重载面板；通常可在更新小组件后注销再登录以清除缓存。
源码脚本的卸载选项只删除辅助程序，测试小组件和插件分别通过各自管理界面移除。

## 手动构建与启动

```sh
python3 tools/build.py
PYTHONPATH=helper python3 -m sptl.server
kpackagetool6 --type Plasma/Applet --install dist/plasma6/org.kde.plasma.sptl
```

Plasma 5 使用 `kpackagetool5` 和 `dist/plasma5/org.kde.plasma.sptl`。
也可以在「安装本地小部件」中选择生成的 `.plasmoid`。
从 KDE Store 安装小部件后，仍需运行辅助程序安装命令，并从 SPlayer 插件市场安装插件。

## 检查连接

```sh
systemctl --user status sptl-bridge.service
journalctl --user -u sptl-bridge.service -n 30
```

未连接辅助程序时显示收起图标及提示；SP 运行但插件未启用时提示启用插件。
正常连接后，SP 无歌曲显示「未在播放 / SPlayer Next」。
辅助服务监听固定的 `127.0.0.1:43827`，端口占用会在服务日志中报告。
连接恢复时重新同步完整歌词；关闭 SP 不会清除共享设置。

主窗口打开优先调用 SP MPRIS Raise，MPRIS 被禁用时使用安装的启动入口。
AppImage 没有桌面入口时请提供 `--splayer-command`。

## 修改设置

右键任务栏中的「SPTL — SPlayer 任务栏歌词」，打开配置窗口。
歌词模式、翻译／音译、字号、封面、宽度、点击行为和主题均在这里修改。
点击“应用”或“确定”保存，取消不会保存未应用的编辑。
“交互与离线”中的“悬停时显示收藏按钮”默认开启，关闭后悬停区恢复三个播放按钮，
歌词弹窗中的收藏按钮仍保留。弹窗的播放模式按钮打开模式菜单，播放列表按钮在列表与歌词间切换。
同组的“即时操作反馈”默认开启，按钮和音量提示先显示目标状态，失败时恢复；
关闭后跟随播放器实际状态，请求仍即时发送。本次按钮并行执行需要更新 SPTL 的 SPlayer 插件脚本。
在任一小部件中应用后，其他 SPTL 小部件会在约 500 ms 内同步；
关闭 SP 或重启辅助程序后仍保留同一套设置。

组件会随任务栏高度实时缩放封面、文字、间距和播放按钮，无需重新添加。
字号设置是组件高 42 像素时的基准，第二行使用第一行的 0.82 倍。
调整任务栏高度后按比例缩放；面板过矮时自动缩小文字，保持两行完整显示。
多个不同高度的面板共用同一基准字号，并按各自可用高度适配。

从旧版本更新时保留辅助程序已保存的配置。已导入的旧 SP 插件暂时可以继续使用，
它的设置不会再覆盖 Plasma 设置；更新市场插件后，SP 内不再提供外观设置表单。

## 更新和卸载

更新辅助程序：重新运行安装命令并选择「升级」，或使用 `python3 tools/install.py --upgrade` 跳过菜单。
升级保留共享设置、自定义启动命令和播放器配置路径。
小组件通过 KDE 商店更新，SPlayer 插件通过官方插件管理更新。
播放模式和播放列表需要对应版本的 SPTL 插件，读取播放列表要求 SP 支持插件 API 5。
收藏通过 SP 的 Linux 托盘菜单执行，需要 `gdbus` 和可用的 SP 托盘入口。
辅助程序更新不会重启 Plasma 面板。小组件更新后若仍显示旧代码，注销后重新登录以清除缓存。
卸载：

```sh
python3 tools/install.py --uninstall
```

此命令只卸载辅助程序，不删除商店小组件或已有插件文件。小组件及 SPlayer 插件分别通过各自管理界面卸载。
辅助程序卸载默认保留 `XDG_STATE_HOME/sptl/settings.json`
（默认 `~/.local/state/sptl/settings.json`），加 `--purge` 删除保存的设置。
脚本仅删除 SPTL 自己的文件，不改动 SP 安装或歌曲数据。
