// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15

Row {
    id: root
    property var bridge
    property real sizeScale: 1
    property bool showFavorite: false
    readonly property real baseWidth: showFavorite ? 118 : 88
    spacing: 2 * sizeScale
    ControlButton {
        objectName: "previousOrDislikeButton"
        bridge: root.bridge
        sizeScale: root.sizeScale
        iconName: bridge.fmActive ? "dislike" : "media-skip-backward"
        commandAction: bridge.fmActive ? "dislike" : "prev"
        commandValue: bridge.fmActive && bridge.track ? ({id: bridge.track.id, source: bridge.track.source, path: bridge.track.path || ""}) : undefined
        enabled: bridge.connected && !!bridge.track && (!bridge.fmActive || bridge.fmAvailable)
        text: bridge.fmActive ? bridge.tr("不喜欢（私人 FM）", "Dislike (Personal FM)") : bridge.tr("上一首", "Previous")
    }
    ControlButton {
        bridge: root.bridge
        sizeScale: root.sizeScale
        iconName: bridge.playing ? "media-playback-pause" : "media-playback-start"
        commandAction: "toggle"
        text: bridge.playing ? bridge.tr("暂停", "Pause") : bridge.tr("播放", "Play")
    }
    ControlButton {
        bridge: root.bridge
        sizeScale: root.sizeScale
        iconName: "media-skip-forward"
        commandAction: "next"
        text: bridge.tr("下一首", "Next")
    }
    FavoriteButton {
        objectName: "hoverFavoriteButton"
        bridge: root.bridge
        sizeScale: root.sizeScale
        visible: root.showFavorite
    }
}
