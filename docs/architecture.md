# 第一版实现结构

- `shared/settings.json`：设置 schema 与默认值的唯一来源。Plasma 原生小部件配置窗口编辑配置。
- `plugin/runtime.js`：构建为官方可导入的独立 JS 脚本。
  API 级别 4，声明 network/control；接收 trackChange、lyricChange、lineChange、
  playStateChange，并每 300 ms 查询 getNowPlaying/getStatus。
- `helper/sptl/`：Python 3.10+ 标准库 HTTP 服务。只绑定 IPv4 loopback，
  统一共享配置、连接状态、主题和本地封面；systemd 用户服务负责重启。
- `plasmoid/contents/ui/`：共用 QML 组件。独立 Plasma 5/6 入口和包元数据，
  最低目标 Plasma 5.27 / Qt 5.15 和 Plasma 6 / Qt 6。

## 协议 v1

SP 插件 POST `/exchange`：session、locale、track、playback、
lyricRevision；歌词变化或连接恢复时附带 lines。响应包含 needLines 和待执行 commands。
每个命令有 ID，插件执行后回传 ack；HTTP 响应丢失会重复投递相同 ID，
插件在执行前记录 ID，防止重复切歌。命令 3 秒过期，断开或新 session 会清空。
这是有界去重机制；插件崩溃瞬间的命令不作跨进程重放。

小部件每 500 ms GET `/state?revision=N`。响应始终包含播放锚点，
内容版本改变时才发送配置、歌曲及完整歌词，避免每次传输大歌词数组。
播放锚点包含 SP 发出的 timestamp、position、speed、offset；
QML 每 33 ms 按时间戳插值，暂停状态不插值，歌词时间为 position + offset。
歌词点击跳转减去 offset；进度条使用歌曲播放时间。

POST `/command` 的启动／唤起由辅助程序执行，其他控制投递给 SP 插件。
GET `/cover` 提供当前歌曲位于 SP covers 缓存目录内的图片，
以及当前 SP MPRIS 发布的 streaming-cover 临时图片，不接受文件路径参数。
POST `/settings` 接收配置窗口已应用的设置补丁，校验并原子保存后更新内容版本。
它不要求 SP 正在运行；多个小部件通过下一次 `/state` 请求接收相同设置。
请求限制 Host/Origin/Fetch-Site；控制和设置请求要求 JSON、自定义客户端标记与运行时
capability，拒绝普通浏览器跨域调用。当前设计针对同一台机器上的桌面集成，
不把同机进程视为隔离的远程客户端。

## 配置和主题

全部外观与交互配置在 Plasma 小部件的原生配置窗口修改，点击“应用”后保存。
`ConfigGeneral.qml` 根据共享 schema 生成中英文表单，使用 `cfg_settingsRequest`
接入 Plasma 的应用／取消流程。`SettingsSync.qml` 在小部件生命周期内发送补丁，
因此点击“确定”后关闭配置窗口不会取消保存；连接暂时中断时自动重试。
小部件配置中的请求仅作为一次编辑记录，重新加载小部件时不重放旧请求。
辅助程序保存的 `XDG_STATE_HOME/sptl/settings.json` 是全局配置的权威来源。
新 SP 插件不注册外观设置或发送设置；旧插件仅在没有已保存配置时迁移一次，
以后不能覆盖 Plasma 中的修改。更新辅助程序即可兼容仍在运行的旧插件。

按用户后续要求，任务栏组件随面板高度自动缩放，字号设置成为组件高 42 像素时的基准值。
通过 `Plasmoid.CanFillArea` 使用完整可用面板高度，避免主题的图标区域边距压缩布局。
封面、间距、文字和播放按钮按当前高度相对 42 像素的比例缩放，封面不再固定封顶 42 像素。
独立测量基准字号的两行文字高度，在面板过矮或基准字号过大时进一步缩小渲染字号，
保持两行完整显示。文字与封面整体垂直居中；按钮在最大宽度不足时缩小到可用空间。
组件的隐式高度始终为 42 像素，最小高度为 16 像素，实际高度由面板分配，
避免内容缩放反过来改变面板高度。多个面板仍共享基准字号，但按各自高度独立适配。

界面动画默认开启，时长取 Kirigami 的 longDuration／shortDuration，跟随 KDE 动画速度；
共享设置 animationsEnabled 可关闭。歌词切换立即更新文本与逐字时间，随后执行淡入和轻微上移，
连续换行会重新开始当前过渡，不延迟播放状态。Taskbar 的 targetWidth 表示最终宽度，
layoutWidth 表示动画中的布局宽度，Plasma 5/6 入口随 layoutWidth 更新宽度提示。
最大宽度降低及离线隐藏立即生效；面板高度变化立即完成尺寸动画，保持内容适配。
控制区的布局宽度和透明度同步变化，退出悬停后立即禁用按钮。
Cover 使用两个异步图片槽，在新图片加载完成前保留当前封面，失败时回退占位图。
完整歌词自动跟随对 contentY 执行有限时长动画，手动滚动会中止动画并保留原有 4 秒恢复规则。

SP 主题和语言的持久化数据实际位于
`Partitions/main/Local Storage/leveldb`，并非主进程 settings.json。
辅助程序只读 WAL 和 SST，支持 Snappy 压缩、序列号和删除记录，不锁定或写入 SP 数据库。
主题和 MPRIS 检查在后台进行，避免阻塞歌词通信。
支持明暗／system、自定义主题色和图片主题中的已持久化背景取色。
封面动态取色没有持久化到 theme store，当前回退 Plasma 主题；
无法读取本地主题时也回退 Plasma，见验证记录。

## 默认细节

双行、优先翻译、单行不优先辅助、基准字号 14／第二行 0.82 倍、
封面左侧、自动宽度、固定宽度 320、自动最大宽度 420（整个部件）、
默认点击完整歌词面板、离线图标、默认启动 SP、歌词点击跳转开启。
鼠标滚轮每步调音量 5%；弹出面板默认 480×560，手动滚动后 4 秒恢复跟随。
前奏／没有歌词时回退歌曲信息，最后一句辅助缺失时第二行空白。
没有时间的歌词可以展示，禁止按该句跳转；逐行歌词不伪造逐字时间。
