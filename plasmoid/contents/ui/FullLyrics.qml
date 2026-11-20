// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC
import QtQuick.Layouts 1.15
import "Logic.js" as Logic

Rectangle {
    id: root
    property var bridge
    property bool following: true
    implicitWidth: 480
    implicitHeight: 560
    Layout.minimumWidth: 320
    Layout.minimumHeight: 360
    Layout.preferredWidth: 480
    Layout.preferredHeight: 560
    color: bridge.background
    radius: 10
    function follow() {
        if (following && bridge.currentIndex >= 0 && lyrics.count)
            lyrics.positionViewAtIndex(bridge.currentIndex, ListView.Center);
    }
    Connections {
        target: bridge
        function onCurrentIndexChanged() { root.follow(); }
        function onLinesChanged() { Qt.callLater(root.follow); }
    }
    onVisibleChanged: { if (visible) { following = true; Qt.callLater(follow); } }
    Timer { id: resume; interval: 4000; onTriggered: { root.following = true; root.follow(); } }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Cover {
                source: bridge.coverSource
                idle: !bridge.track
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
                }
                Marquee {
                    Layout.fillWidth: true
                    text: bridge.track ? bridge.track.artists || bridge.tr("未知艺术家", "Unknown artist") : "SPlayer Next"
                    pixelSize: 14
                    textColor: bridge.secondary
                }
            }
        }
        ListView {
            id: lyrics
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: bridge.lines
            boundsBehavior: Flickable.StopAtBounds
            QQC.ScrollBar.vertical: QQC.ScrollBar {}
            onMovementStarted: { root.following = false; resume.stop(); }
            onMovementEnded: resume.restart()
            onModelChanged: Qt.callLater(root.follow)
            delegate: Rectangle {
                id: lineDelegate
                property var line: modelData
                property bool active: index === bridge.currentIndex
                width: lyrics.width
                height: lyricColumn.implicitHeight + 20
                color: active ? Qt.rgba(bridge.accent.r, bridge.accent.g, bridge.accent.b, 0.12) : "transparent"
                radius: 7
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
        Text {
            Layout.fillWidth: true
            visible: bridge.lastError.length > 0
            text: bridge.lastError
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
            Controls { bridge: root.bridge }
            Item { Layout.fillWidth: true }
            Text { text: Logic.formatTime(bridge.playback.duration); color: bridge.secondary }
        }
    }
}
