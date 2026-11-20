// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15

Row {
    id: root
    property var bridge
    property real sizeScale: 1
    spacing: 2 * sizeScale
    ControlButton {
        bridge: root.bridge
        sizeScale: root.sizeScale
        iconName: "media-skip-backward"
        commandAction: "prev"
        text: bridge.tr("上一首", "Previous")
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
}
