// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC
import QtQuick.Layouts 1.15

ColumnLayout {
    id: root
    property var bridge
    property var tracks: []
    property int shownOffset: -1
    readonly property string tracksRevision: JSON.stringify([bridge.queue.offset, bridge.queue.tracks, bridge.queue.error])
    onTracksRevisionChanged: {
        tracks = bridge.queue.error ? [] : bridge.queue.tracks;
        if (shownOffset !== bridge.queue.offset) {
            shownOffset = bridge.queue.offset;
            Qt.callLater(function() { list.positionViewAtBeginning(); });
        }
    }
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: bridge.tr("播放列表", "Playlist") + " · " + bridge.queue.total
            color: bridge.foreground
            font.pixelSize: 16
        }
        QQC.Button {
            objectName: "refreshQueue"
            text: bridge.tr("刷新", "Refresh")
            enabled: bridge.connected && !bridge.queueLoading
            onClicked: bridge.requestQueue(bridge.queue.offset)
        }
    }
    ListView {
        id: list
        objectName: "playbackQueueList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: root.tracks
        spacing: 4
        boundsBehavior: Flickable.StopAtBounds
        QQC.ScrollBar.vertical: QQC.ScrollBar {}
        delegate: QQC.ItemDelegate {
            id: row
            property var track: modelData
            property int queueIndex: bridge.queue.offset + index
            objectName: "queueTrack_" + queueIndex
            width: list.width
            height: 56
            enabled: bridge.connected && bridge.queue.available
            highlighted: queueIndex === bridge.queue.currentIndex
            onClicked: bridge.command("queuePlay", {index: queueIndex, id: track.id, source: track.source, path: track.path || ""})
            contentItem: RowLayout {
                spacing: 10
                Text {
                    text: row.queueIndex + 1
                    color: row.highlighted ? bridge.accent : bridge.secondary
                    Layout.preferredWidth: 28
                    horizontalAlignment: Text.AlignHCenter
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 3
                    Text {
                        Layout.fillWidth: true
                        text: row.track.title
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: row.highlighted ? bridge.accent : bridge.foreground
                        font.pixelSize: 15
                    }
                    Text {
                        Layout.fillWidth: true
                        text: row.track.artists || bridge.tr("未知艺术家", "Unknown artist")
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: bridge.secondary
                        font.pixelSize: 12
                    }
                }
            }
            background: Rectangle {
                radius: 6
                color: row.highlighted ? Qt.rgba(bridge.accent.r, bridge.accent.g, bridge.accent.b, 0.14) :
                    row.hovered ? Qt.rgba(bridge.foreground.r, bridge.foreground.g, bridge.foreground.b, 0.06) : "transparent"
            }
        }
        Text {
            anchors.centerIn: parent
            width: parent.width - 20
            visible: list.count === 0
            text: !bridge.connected ? bridge.statusText() : bridge.queueLoading ? bridge.tr("正在读取播放列表…", "Loading playlist…") :
                !bridge.queue.available ? bridge.tr("请更新 SP 和 SPTL 插件以读取播放列表", "Update SP and the SPTL plugin to view the playlist") :
                bridge.queue.error ? bridge.tr("播放列表读取失败，请刷新重试", "Could not read the playlist; refresh to retry") :
                bridge.tr("播放列表为空", "The playlist is empty")
            color: bridge.secondary
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
    RowLayout {
        Layout.fillWidth: true
        visible: bridge.queue.total > 50
        QQC.Button {
            objectName: "previousQueuePage"
            text: bridge.tr("上一页", "Previous")
            enabled: bridge.connected && !bridge.queueLoading && bridge.queue.offset > 0
            onClicked: bridge.requestQueue(Math.max(0, bridge.queue.offset - 50))
        }
        Text {
            Layout.fillWidth: true
            text: (bridge.queue.offset + 1) + "–" + (bridge.queue.offset + bridge.queue.tracks.length) + " / " + bridge.queue.total
            color: bridge.secondary
            horizontalAlignment: Text.AlignHCenter
        }
        QQC.Button {
            objectName: "nextQueuePage"
            text: bridge.tr("下一页", "Next")
            enabled: bridge.connected && !bridge.queueLoading && bridge.queue.offset + bridge.queue.tracks.length < bridge.queue.total
            onClicked: bridge.requestQueue(bridge.queue.offset + 50)
        }
    }
}
