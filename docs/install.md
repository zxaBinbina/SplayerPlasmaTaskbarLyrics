# 用户级安装与维护

## 常规安装

执行 `python3 tools/install.py`，无需 sudo。脚本构建插件和小部件，
安装到 XDG 用户数据目录，并启用 `sptl-bridge.service` 用户服务。
SP 插件需要通过官方插件管理页面导入，脚本不会修改 SP 的私有配置。

版本检测优先读取 KDE_SESSION_VERSION，否则以 Qt 离屏模式运行 `plasmashell --version`，无需连接显示服务。
从桌面外启动的终端会尝试当前用户的 `/run/user/<uid>/bus`；若没有可用用户会话，安装前会明确提示。
可显式选择 `--plasma 5` 或 `--plasma 6`。两种安装包使用同一个小部件 ID；
同一用户的数据目录保留一套安装，切换 Plasma 主版本时重新安装对应包。

## AppImage 或自定义数据目录

```sh
python3 tools/install.py --plasma 6 \
  --splayer-command '/path/to/SPlayer-Next.AppImage' \
  --splayer-config '/path/to/SPlayer-Next/app-data/config/settings.json'
```

服务配置中的这些参数用于程序定位，不属于第二套外观设置。
标准安装会尝试 XDG_CONFIG_HOME 下的 SPlayer-Next、splayer-next、splayer_next
以及 Flatpak 配置目录。SP 封面缓存位置跟随它的 `cache.dir`。

## 手动构建与启动

```sh
python3 tools/build.py
PYTHONPATH=helper python3 -m sptl.server
kpackagetool6 --type Plasma/Applet --install dist/plasma6/org.kde.plasma.sptl
```

Plasma 5 使用 `kpackagetool5` 和 `dist/plasma5/org.kde.plasma.sptl`。
也可以在「安装本地小部件」中选择生成的 `.plasmoid`。
只从 KDE Store 安装小部件时，仍需另外安装辅助程序并导入 SP 插件。

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
在任一小部件中应用后，其他 SPTL 小部件会在约 500 ms 内同步；
关闭 SP 或重启辅助程序后仍保留同一套设置。

组件会随任务栏高度实时缩放封面、文字、间距和播放按钮，无需重新添加。
字号设置是组件高 42 像素时的基准，第二行使用第一行的 0.82 倍。
调整任务栏高度后按比例缩放；面板过矮时自动缩小文字，保持两行完整显示。
多个不同高度的面板共用同一基准字号，并按各自可用高度适配。

从旧版本更新时保留辅助程序已保存的配置。已导入的旧 SP 插件暂时可以继续使用，
它的设置不会再覆盖 Plasma 设置；重新导入新插件后，SP 内不再提供外观设置表单。

## 更新和卸载

更新：重新运行安装命令，并在 SP 中重新导入生成的同 ID 插件。
播放模式和播放列表需要本次新版 SPTL 插件；读取播放列表还要求 SP 支持插件 API 5。
收藏通过 SP 的 Linux 托盘菜单执行，需要 `gdbus` 和可用的 SP 托盘入口，
不需要增加插件权限；收藏高亮跟随 SP 的真实状态，不支持的歌曲沿用 SP 的提示。
Plasma 在进程内缓存 QML 组件，移除后重新添加也可能继续运行旧代码。
例如旧组件仍按任务栏高度把 32 像素压至约 8 像素，而磁盘代码和设置已经更新。
使用以下命令更新并丢弃旧组件缓存：

```sh
python3 tools/install.py --reload-plasma
```

此选项重启正在运行的 `plasma-plasmashell.service`，面板和桌面短暂重载，
应用窗口保留。仅支持该用户服务正在运行的桌面；否则安装前会明确停止，
可选择普通更新后注销再登录。默认安装不会重启 Plasma。
卸载：

```sh
python3 tools/install.py --uninstall
```

在 SP 插件管理中删除插件。卸载默认保留 `XDG_STATE_HOME/sptl/settings.json`
（默认 `~/.local/state/sptl/settings.json`），加 `--purge` 删除保存的设置。
脚本仅删除 SPTL 自己的文件，不改动 SP 安装或歌曲数据。
