// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC
import QtQuick.Layouts 1.15
import "Logic.js" as Logic

Rectangle {
    id: root
    property var bridge
    property bool following: true
    property bool playlistShown: false
    property real pendingVolume: -1
    readonly property string playbackMode: Logic.playMode(bridge.playback)
    implicitWidth: 480
    implicitHeight: 560
    Layout.minimumWidth: 320
    Layout.minimumHeight: 360
    Layout.preferredWidth: 480
    Layout.preferredHeight: 560
    color: bridge.background
    radius: 10
    function follow(immediate) {
        if (!visible || playlistShown || !following || bridge.currentIndex < 0 || !lyrics.count) return;
        scrollMotion.stop();
        var previous = lyrics.contentY;
        lyrics.positionViewAtIndex(bridge.currentIndex, ListView.Center);
        var destination = lyrics.contentY;
        if (!immediate && bridge.motionDuration > 0 && Math.abs(destination - previous) > 1) {
            lyrics.contentY = previous;
            scrollMotion.to = destination;
            scrollMotion.start();
        }
    }
    NumberAnimation {
        id: scrollMotion
        target: lyrics; property: "contentY"
        duration: bridge.motionDuration * 1.5; easing.type: Easing.OutCubic
    }
    Connections {
        target: bridge
        function onCurrentIndexChanged() { Qt.callLater(root.follow); }
        function onLinesChanged() {
            scrollMotion.stop();
            Qt.callLater(function() { root.follow(true); });
        }
        function onMotionDurationChanged() { if (bridge.motionDuration === 0) scrollMotion.complete(); }
    }
    onVisibleChanged: {
        if (visible) { following = true; Qt.callLater(function() { root.follow(true); }); }
        else { scrollMotion.stop(); resume.stop(); playlistShown = false; }
    }
    onPlaylistShownChanged: {
        if (playlistShown) { scrollMotion.stop(); bridge.requestQueue(); }
        else Qt.callLater(function() { root.follow(true); });
    }
    Timer {
        interval: 2000; repeat: true
        running: root.visible && root.playlistShown && bridge.connected
        onTriggered: bridge.requestQueue(bridge.queue.offset)
    }
    Timer { id: resume; interval: 4000; onTriggered: { root.following = true; root.follow(); } }
    function commitVolume() {
        volumeCommit.stop();
        if (pendingVolume < 0 || !bridge.connected) return;
        bridge.command("setVolume", pendingVolume);
        pendingVolume = -1;
        volumeHold.restart();
    }
    Timer { id: volumeCommit; interval: 120; onTriggered: root.commitVolume() }
    Timer { id: volumeHold; interval: 700 }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Cover {
                objectName: "popupCover"
                source: bridge.coverSource
                idle: !bridge.track
                circular: bridge.settings.coverShape === "circle"
                rotateWhilePlaying: bridge.settings.rotateCover === true
                playing: bridge.playing
                transitionDuration: bridge.motionDuration
                Layout.preferredWidth: 72
                Layout.preferredHeight: 72
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Marquee {
                    Layout.fillWidth: true
                    text: bridge.track ? bridge.track.title : bridge.statusText()
                    pixelSize: 19
                    textColor: bridge.foreground
                    transitionDuration: bridge.motionDuration
                }
                Marquee {
                    Layout.fillWidth: true
                    text: bridge.track ? bridge.track.artists || bridge.tr("未知艺术家", "Unknown artist") : "SPlayer Next"
                    pixelSize: 14
                    textColor: bridge.secondary
                    transitionDuration: bridge.motionDuration
                }
            }
            QQC.Button {
                objectName: "openSPlayerButton"
                text: bridge.tr("打开 SPlayer", "Open SPlayer")
                enabled: bridge.reachable
                onClicked: bridge.command("open")
            }
        }
        ListView {
            id: lyrics
            objectName: "fullLyricsList"
            visible: !root.playlistShown
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: bridge.lines
            boundsBehavior: Flickable.StopAtBounds
            QQC.ScrollBar.vertical: QQC.ScrollBar {}
            onMovementStarted: { root.following = false; scrollMotion.stop(); resume.stop(); }
            onMovementEnded: { if (!root.following) resume.restart(); }
            onModelChanged: Qt.callLater(function() { root.follow(true); })
            delegate: Rectangle {
                id: lineDelegate
                property var line: modelData
                property bool active: index === bridge.currentIndex
                width: lyrics.width
                height: lyricColumn.implicitHeight + 20
                color: active ? Qt.rgba(bridge.accent.r, bridge.accent.g, bridge.accent.b, 0.12) : "transparent"
                radius: 7
                Behavior on color {
                    ColorAnimation { duration: bridge.motionDuration }
                }
                Column {
                    id: lyricColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 10
                    spacing: 4
                    Marquee {
                        width: parent.width
                        text: lineDelegate.line.text
                        pixelSize: 18
                        textColor: bridge.foreground
                        highlightColor: bridge.accent
                        lineActive: lineDelegate.active
                        words: lineDelegate.active && lineDelegate.line.wordTimed ? lineDelegate.line.words : []
                        position: bridge.lyricPosition
                    }
                    Marquee {
                        width: parent.width
                        visible: text.length > 0
                        text: Logic.auxiliary(lineDelegate.line, bridge.settings.auxiliary)
                        pixelSize: 14
                        textColor: bridge.secondary
                        highlightColor: bridge.accent
                        words: lineDelegate.active ? Logic.auxiliaryWords(lineDelegate.line, bridge.settings.auxiliary) : []
                        position: bridge.lyricPosition
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: bridge.connected && bridge.settings.clickLyricSeek && lineDelegate.line.timed
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: bridge.command("seek", Math.max(0, lineDelegate.line.startTime - bridge.playback.offset))
                }
            }
            Text {
                anchors.centerIn: parent
                width: parent.width - 16
                visible: lyrics.count === 0
                text: bridge.track ? bridge.tr("暂无歌词", "No lyrics available") : bridge.statusText()
                color: bridge.secondary
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
            }
        }
        PlaybackQueue {
            objectName: "playbackQueue"
            bridge: root.bridge
            visible: root.playlistShown
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
        Text {
            Layout.fillWidth: true
            visible: text.length > 0
            text: bridge.lastError || bridge.actionError
            color: bridge.accent
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
        }
        QQC.Slider {
            id: progress
            Layout.fillWidth: true
            from: 0
            to: Math.max(1, bridge.playback.duration)
            enabled: bridge.connected && !!bridge.track && bridge.playback.duration > 0
            Binding { target: progress; property: "value"; value: bridge.position; when: !progress.pressed; restoreMode: Binding.RestoreBindingOrValue }
            onPressedChanged: { if (!pressed && enabled) bridge.command("seek", value); }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: Logic.formatTime(progress.value); color: bridge.secondary }
            Item { Layout.fillWidth: true }
            ControlButton {
                id: modeButton
                objectName: "playbackModeButton"
                bridge: root.bridge
                iconName: root.playbackMode === "shuffle" ? "shuffle" : root.playbackMode === "one" ? "repeat-one" : "repeat"
                checked: root.playbackMode !== "list"
                enabled: bridge.connected && !!bridge.track && bridge.modeAvailable
                text: bridge.tr("播放模式：", "Playback mode: ") + (root.playbackMode === "shuffle" ? bridge.tr("随机播放", "Shuffle") :
                    root.playbackMode === "one" ? bridge.tr("单曲循环", "Repeat one") : bridge.tr("列表循环", "Repeat all"))
                onClicked: modeMenu.popup()
                QQC.Menu {
                    id: modeMenu
                    objectName: "playbackModeMenu"
                    QQC.MenuItem {
                        objectName: "mode_list"
                        text: bridge.tr("列表循环", "Repeat all")
                        checkable: true; checked: root.playbackMode === "list"
                        onTriggered: bridge.command("mode", "list")
                    }
                    QQC.MenuItem {
                        objectName: "mode_one"
                        text: bridge.tr("单曲循环", "Repeat one")
                        checkable: true; checked: root.playbackMode === "one"
                        onTriggered: bridge.command("mode", "one")
                    }
                    QQC.MenuItem {
                        objectName: "mode_shuffle"
                        text: bridge.tr("随机播放", "Shuffle")
                        checkable: true; checked: root.playbackMode === "shuffle"
                        onTriggered: bridge.command("mode", "shuffle")
                    }
                }
            }
            Controls { objectName: "popupControls"; bridge: root.bridge }
            FavoriteButton { objectName: "popupFavoriteButton"; bridge: root.bridge }
            ControlButton {
                objectName: "playlistButton"
                bridge: root.bridge
                iconName: "playlist"
                checked: root.playlistShown
                text: root.playlistShown ? bridge.tr("返回歌词", "Back to lyrics") : bridge.tr("播放列表", "Playlist")
                onClicked: root.playlistShown = !root.playlistShown
            }
            Item { Layout.fillWidth: true }
            Text { text: Logic.formatTime(bridge.playback.duration); color: bridge.secondary }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                text: bridge.tr("音量", "Volume")
                color: bridge.secondary
            }
            QQC.Slider {
                id: volume
                objectName: "volumeSlider"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                from: 0; to: 1; stepSize: 0.01
                enabled: bridge.connected
                Accessible.name: bridge.tr("SPlayer 音量", "SPlayer volume")
                Binding {
                    target: volume; property: "value"
                    value: bridge.playback.volume === undefined ? 1 : bridge.playback.volume
                    when: !volume.pressed && !volumeCommit.running && !volumeHold.running
                    restoreMode: Binding.RestoreNone
                }
                onMoved: {
                    root.pendingVolume = value;
                    if (!volumeCommit.running) volumeCommit.start();
                }
                onPressedChanged: { if (!pressed) root.commitVolume(); }
            }
            Text {
                objectName: "volumePercentage"
                text: Math.round(volume.value * 100) + "%"
                color: bridge.secondary
                horizontalAlignment: Text.AlignRight
                Layout.preferredWidth: 42
            }
        }
    }
}
