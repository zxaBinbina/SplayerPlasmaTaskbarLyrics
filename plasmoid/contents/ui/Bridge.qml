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
    property int commandSerial: 0
    property int errorSerial: 0
    property var requestRecords: []
    property var outgoingRequests: ({})
    property var commandResults: []
    signal commandFinished(int requestId, string action, bool success)
    property bool savingSettings: false
    readonly property var settings: Object.assign({}, Defaults.settings, content.settings)
    readonly property int motionDuration: settings.animationsEnabled === false ? 0 : Kirigami.Units.longDuration
    readonly property int quickDuration: settings.animationsEnabled === false ? 0 : Kirigami.Units.shortDuration
    readonly property bool instantFeedback: settings.instantFeedback !== false
    readonly property var track: content.track
    readonly property var lines: content.lines
    readonly property var queue: content.queue || ({available: false, tracks: [], total: 0, currentIndex: -1, offset: 0, requestId: 0, error: ""})
    readonly property bool modeAvailable: content.modeAvailable === true
    readonly property bool fmActive: connected && content.fmActive === true
    readonly property bool fmAvailable: connected && content.fmAvailable === true
    readonly property bool favoriteAvailable: !!content.favorite && content.favorite.available === true
    readonly property bool favoriteLiked: feedbackValue("favorite", !!content.favorite && content.favorite.liked === true)
    readonly property string playbackState: feedbackValue("state", playback.state)
    readonly property string playbackMode: feedbackValue("mode", Logic.playMode(playback))
    readonly property int queueSelectionIndex: feedbackValue("selection", null) === null ? queue.currentIndex : feedbackValue("selection", null).index
    readonly property real volume: feedbackValue("volume", playback.volume === undefined ? 1 : playback.volume)
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
    readonly property bool playing: connected && playbackState === "playing"
    readonly property bool hidden: !running && settings.offlineDisplay === "hidden"
    readonly property bool chinese: String(content.locale).toLowerCase().indexOf("zh") === 0
    readonly property real position: projectedPosition()
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
    function trackKey(track) {
        return track ? JSON.stringify([track.id, track.source || "", track.path || ""]) : "";
    }
    function feedbackSlot(action) {
        return action === "toggle" ? "state" : action === "queuePlay" ? "selection" :
            action === "setVolume" ? "volume" : ["prev", "next", "dislike", "startLiked"].indexOf(action) >= 0 ? "navigation" : action;
    }
    function feedbackRecord(slot) {
        if (!instantFeedback) return null;
        for (var i = requestRecords.length - 1; i >= 0; --i) {
            var record = requestRecords[i];
            if (record.slot === slot && (!record.trackBound || record.track === trackKey(track))) return record;
        }
        return null;
    }
    function feedbackValue(slot, fallback) {
        var record = feedbackRecord(slot);
        return record ? record.value : fallback;
    }
    function actionPending(action) {
        if (!instantFeedback) return false;
        return requestRecords.some(function(record) {
            return record.action === action && (!record.trackBound || record.track === trackKey(bridge.track));
        });
    }
    function projectedPosition() {
        var source = feedbackRecord("seek"), state = feedbackRecord("state");
        if (state && state.track !== trackKey(track)) state = null;
        if (state && (!source || state.id > source.id)) source = state;
        var base = source ? source.slot === "seek" ? source.value : source.position : playback.position;
        var timestamp = source ? source.at : playback.timestamp;
        return Math.max(0, Math.min(playback.duration > 0 ? playback.duration : Infinity,
            base + (playing ? Math.max(0, clockMs - timestamp) * playback.speed : 0)));
    }
    function feedbackConfirmed(record) {
        if (!record.complete) return false;
        if (record.outcomeConfirmed && record.slot === "volume") return true;
        if (record.slot === "state") return playback.state === record.value;
        if (record.slot === "favorite") return !!content.favorite && content.favorite.liked === record.value;
        if (record.slot === "mode") return Logic.playMode(playback) === record.value;
        if (record.slot === "seek") return Math.abs(playback.position - record.value) < 750;
        if (record.slot === "selection") return queue.currentIndex === record.value.index && trackKey(track) === trackKey(record.value);
        if (record.slot === "volume") return pendingVolume === null && Math.abs(playback.volume - record.value) < 0.00001;
        return Date.now() - record.at >= 160;
    }
    function failCommand(id, action) {
        clockMs = Date.now();
        requestRecords = requestRecords.filter(function(record) { return record.id !== id; });
        if (id >= errorSerial) {
            errorSerial = id;
            lastError = tr("操作失败，请检查 SP 与辅助程序", "Action failed; check SP and the bridge");
        }
        if (action === "queue") queueLoading = false;
        commandFinished(id, action, false);
    }
    function settleFeedback() {
        var failures = [], confirmed = {}, now = Date.now();
        requestRecords = requestRecords.map(function(record) {
            var outcome = commandResults.find(function(result) { return result.id === record.serverId; });
            if (outcome && !outcome.ok) failures.push(record);
            if (outcome && outcome.ok) record = Object.assign({}, record, {complete: true, outcomeConfirmed: true});
            if (record.status === "accepted" && feedbackConfirmed(record))
                confirmed[record.slot] = Math.max(confirmed[record.slot] || 0, record.id);
            return record;
        }).filter(function(record) {
            return (!record.trackBound || record.track === trackKey(track)) && record.id > (confirmed[record.slot] || 0);
        });
        failures.forEach(function(record) { bridge.failCommand(record.id, record.action); });
        Object.keys(outgoingRequests).forEach(function(id) {
            var entry = outgoingRequests[id];
            if (now - entry.at > 3000) {
                delete outgoingRequests[id]; entry.request.abort();
                bridge.failCommand(Number(id), entry.action);
            }
        });
        requestRecords.slice().forEach(function(record) {
            if (record.status === "accepted" && now - record.at > 15000) {
                bridge.failCommand(record.id, record.action);
            }
        });
    }
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
                    commandResults = result.commandResults || [];
                    revision = result.revision;
                    token = result.token;
                    lastSuccess = Date.now();
                    reachable = true;
                    settleFeedback();
                } catch (error) { revision = -1; }
            }
        };
        request.open("GET", endpoint + "/state?revision=" + revision);
        request.send();
    }
    function command(action, value, osd) {
        var id = ++commandSerial;
        if (!token) {
            lastError = statusText();
            Qt.callLater(function() { bridge.commandFinished(id, action, false); });
            return id;
        }
        if (action === "toggle") value = playing ? "paused" : "playing";
        var preview = action === "favorite" ? !favoriteLiked : value;
        var record = {id: id, action: action, slot: feedbackSlot(action), value: preview,
                      at: Date.now(), position: position, track: trackKey(track),
                      trackBound: ["favorite", "seek", "queuePlay", "prev", "next", "dislike"].indexOf(action) >= 0,
                      status: "sending", serverId: -1, complete: false};
        requestRecords = requestRecords.concat([record]);
        var request = new XMLHttpRequest();
        outgoingRequests[id] = {request: request, at: record.at, action: action};
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE || !outgoingRequests[id] || outgoingRequests[id].request !== request) return;
            delete outgoingRequests[id];
            var response = null;
            try { if (request.status === 200) response = JSON.parse(request.responseText); } catch (error) {}
            if (!response) { bridge.failCommand(id, action); return; }
            if (id >= errorSerial) { errorSerial = id; lastError = ""; }
            if (response.superseded) requestRecords = requestRecords.filter(function(entry) { return entry.id !== id; });
            else requestRecords = requestRecords.map(function(entry) {
                return entry.id === id ? Object.assign({}, entry, {status: "accepted", serverId: response.id || -1,
                    complete: response.native === true || response.ok === true}) : entry;
            });
            bridge.commandFinished(id, action, true);
            bridge.settleFeedback();
            bridge.poll();
        };
        request.open("POST", endpoint + "/command");
        request.setRequestHeader("Content-Type", "application/json");
        request.setRequestHeader("X-SPTL-Client", "plasma");
        var payload = { token: token, action: action, value: value === undefined ? null : value, osd: osd === true,
                        inputClient: volumeClient, inputSequence: id };
        if (action === "favorite") payload.favoriteLiked = preview;
        if (action === "seek" && track) payload.targetTrack = {id: track.id, source: track.source || "", path: track.path || ""};
        if (action === "setVolume") {
            payload.volumeClient = volumeClient;
            payload.volumeSequence = ++volumeSequence;
        }
        request.send(JSON.stringify(payload));
        return id;
    }
    function requestQueue(offset) {
        if (!connected || queueLoading) return -1;
        queueLoading = true;
        queueRequestedAt = Date.now();
        return command("queue", offset === undefined ? -1 : offset);
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
        interval: 80; running: bridge.requestRecords.length > 0 || Object.keys(bridge.outgoingRequests).length > 0; repeat: true
        onTriggered: bridge.settleFeedback()
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
    Component.onDestruction: {
        if (pending) pending.abort();
        Object.keys(outgoingRequests).forEach(function(id) { outgoingRequests[id].request.abort(); });
    }
}
