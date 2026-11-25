// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import org.kde.kirigami 2.20 as Kirigami
import "Defaults.js" as Defaults
import "Logic.js" as Logic

Item {
    id: bridge
    width: 0
    height: 0
    property string endpoint: "http://127.0.0.1:43827"
    property var content: ({ settings: Defaults.settings, track: null, lines: [], locale: "zh-CN",
                             theme: ({available: false}), running: false, pluginConnected: false })
    property var playback: ({ state: "stopped", position: 0, duration: 0, speed: 1, offset: 0, timestamp: 0 })
    property var pendingVolume: null
    property string volumeClient: Date.now().toString(36) + Math.random().toString(36)
    property int volumeSequence: 0
    property int revision: -1
    property string token: ""
    property bool reachable: false
    property double lastSuccess: 0
    property double clockMs: Date.now()
    property var pending: null
    property double pendingSince: 0
    property string lastError: ""
    property bool savingSettings: false
    readonly property var settings: content.settings
    readonly property int motionDuration: settings.animationsEnabled === false ? 0 : Kirigami.Units.longDuration
    readonly property int quickDuration: settings.animationsEnabled === false ? 0 : Kirigami.Units.shortDuration
    readonly property var track: content.track
    readonly property var lines: content.lines
    readonly property var queue: content.queue || ({available: false, tracks: [], total: 0, currentIndex: -1, offset: 0, requestId: 0, error: ""})
    readonly property bool modeAvailable: content.modeAvailable === true
    readonly property bool fmActive: connected && content.fmActive === true
    readonly property bool fmAvailable: connected && content.fmAvailable === true
    readonly property bool favoriteAvailable: !!content.favorite && content.favorite.available === true
    readonly property bool favoriteLiked: !!content.favorite && content.favorite.liked === true
    readonly property string actionError: content.commandError === "queue_changed" ?
        tr("播放列表已改变，请刷新后重试", "The playlist changed; refresh and try again") :
        content.commandError === "queue_unavailable" ? tr("此版本 SP 不支持读取播放列表", "This SP version cannot read the playlist") :
        content.commandError === "fm_changed" ? tr("私人 FM 曲目已变化，请重试", "The FM song changed; try again") :
        content.commandError === "login_required" ? tr("请先在 SPlayer 登录网易云音乐", "Sign in to NetEase Music in SPlayer first") :
        content.commandError === "liked_empty" ? tr("我喜欢的音乐中暂无可播放歌曲", "No playable liked songs") :
        content.commandError === "start_unavailable" ? tr("请更新 SPlayer 和 SPTL 插件，并允许 API 权限", "Update SPlayer and SPTL, and allow API access") :
        content.commandError === "control_failed" ? tr("SP 操作失败，请重试", "SP action failed; try again") : ""
    property bool queueLoading: false
    property double queueRequestedAt: 0
    readonly property int queueResponseId: queue.requestId || 0
    onQueueResponseIdChanged: queueLoading = false
    readonly property bool running: reachable && content.running
    readonly property bool connected: reachable && content.pluginConnected
    readonly property bool playing: connected && playback.state === "playing"
    readonly property bool hidden: !running && settings.offlineDisplay === "hidden"
    readonly property bool chinese: String(content.locale).toLowerCase().indexOf("zh") === 0
    readonly property real position: Math.max(0, Math.min(playback.duration > 0 ? playback.duration : Infinity,
        playback.position + (playing ? Math.max(0, clockMs - playback.timestamp) * playback.speed : 0)))
    readonly property real lyricPosition: position + playback.offset
    readonly property int currentIndex: Logic.currentIndex(lines, lyricPosition)
    readonly property var theme: content.theme || ({ available: false })
    readonly property bool plasmaTheme: settings.themeMode === "plasma" ||
        (settings.themeMode === "splayer" && (!reachable || !theme.available))
    readonly property bool plasmaDark: Kirigami.Theme.backgroundColor.r +
        Kirigami.Theme.backgroundColor.g + Kirigami.Theme.backgroundColor.b < 1.5
    readonly property bool dark: plasmaTheme ? plasmaDark : settings.themeMode === "manual" ?
        settings.manualDark : theme.mode === "system" ? plasmaDark : theme.mode === "dark"
    readonly property color foreground: plasmaTheme ? Kirigami.Theme.textColor : dark ? "#f5f5f5" : "#202124"
    readonly property color secondary: plasmaTheme ? Kirigami.Theme.disabledTextColor : dark ? "#b9b9bd" : "#656569"
    readonly property color background: plasmaTheme ? Kirigami.Theme.backgroundColor : dark ? "#202124" : "#fafafa"
    readonly property color accent: plasmaTheme ? Kirigami.Theme.highlightColor :
        settings.themeMode === "manual" ? settings.manualAccent : theme.accent || "#fe7971"
    readonly property string coverSource: {
        if (!track) return "../images/splayer.svg";
        var cover = track.cover || "";
        if (/^https?:\/\//.test(cover) || /^data:image\/(png|jpeg|webp|gif);base64,/.test(cover)) return cover;
        if (/^(cache|cover|streaming-cover):\/\//.test(cover))
            return endpoint + "/cover?token=" + encodeURIComponent(token) + "&revision=" + revision;
        return "../images/placeholder.svg";
    }
    function tr(zh, en) { return chinese ? zh : en; }
    function statusText() {
        if (!reachable) return tr("歌词辅助程序未连接", "Lyrics bridge unavailable");
        if (!running) return tr("SPlayer Next 未运行", "SPlayer Next is closed");
        if (!connected) return tr("请在 SP 中启用 SPTL 插件", "Enable the SPTL plugin in SP");
        return tr("未在播放", "Not playing");
    }
    function poll() {
        if (pending) {
            if (Date.now() - pendingSince > 2000) {
                var old = pending; pending = null; old.abort();
            } else return;
        }
        var request = new XMLHttpRequest();
        pending = request;
        pendingSince = Date.now();
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE || pending !== request) return;
            pending = null;
            if (request.status === 200) {
                try {
                    var result = JSON.parse(request.responseText);
                    if (result.protocol !== 1) return;
                    if (result.content) content = result.content;
                    pendingVolume = result.pendingVolume === undefined ? null : result.pendingVolume;
                    playback = result.playback;
                    revision = result.revision;
                    token = result.token;
                    lastSuccess = Date.now();
                    reachable = true;
                } catch (error) { revision = -1; }
            }
        };
        request.open("GET", endpoint + "/state?revision=" + revision);
        request.send();
    }
    function command(action, value, osd) {
        if (!token) { lastError = statusText(); return; }
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
            if (request.readyState === XMLHttpRequest.DONE) {
                if (action === "queue" && request.status !== 200) queueLoading = false;
                lastError = request.status === 200 ? "" :
                    tr("操作失败，请检查 SP 与辅助程序", "Action failed; check SP and the bridge");
            }
        };
        request.open("POST", endpoint + "/command");
        request.setRequestHeader("Content-Type", "application/json");
        request.setRequestHeader("X-SPTL-Client", "plasma");
        var payload = { token: token, action: action, value: value === undefined ? null : value, osd: osd === true };
        if (action === "setVolume" && osd === true) {
            payload.volumeClient = volumeClient;
            payload.volumeSequence = ++volumeSequence;
        }
        request.send(JSON.stringify(payload));
    }
    function requestQueue(offset) {
        if (!connected || queueLoading) return;
        queueLoading = true;
        queueRequestedAt = Date.now();
        command("queue", offset === undefined ? -1 : offset);
    }
    function saveSettings(changes, callback) {
        if (!reachable || !token || savingSettings) return false;
        savingSettings = true;
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) return;
            savingSettings = false;
            var success = request.status === 200;
            lastError = success ? "" : tr("设置保存失败，将自动重试", "Saving settings failed; retrying");
            if (success) { revision = -1; poll(); }
            callback(success);
        };
        request.open("POST", endpoint + "/settings");
        request.setRequestHeader("Content-Type", "application/json");
        request.setRequestHeader("X-SPTL-Client", "plasma");
        request.send(JSON.stringify({token: token, settings: changes}));
        return true;
    }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            bridge.poll();
            if (bridge.queueLoading && Date.now() - bridge.queueRequestedAt > 6000) bridge.queueLoading = false;
            if (Date.now() - bridge.lastSuccess > 5000) {
                bridge.reachable = false;
                bridge.revision = -1;
            }
        }
    }
    Timer {
        interval: 33; running: bridge.playing; repeat: true
        onTriggered: bridge.clockMs = Date.now()
    }
    onPlaybackChanged: clockMs = Date.now()
    Component.onCompleted: poll()
    Component.onDestruction: { if (pending) pending.abort(); }
}
