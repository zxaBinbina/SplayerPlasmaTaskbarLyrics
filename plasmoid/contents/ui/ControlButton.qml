// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC

QQC.ToolButton {
    id: root
    property var bridge
    property real sizeScale: 1
    property string iconName: ""
    property string commandAction: ""
    implicitWidth: 28 * sizeScale
    implicitHeight: 28 * sizeScale
    enabled: bridge.connected && !!bridge.track
    contentItem: Item {
        implicitWidth: 18 * root.sizeScale
        implicitHeight: 18 * root.sizeScale
        Canvas {
            id: glyph
            anchors.centerIn: parent
            width: 18 * root.sizeScale
            height: 18 * root.sizeScale
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                ctx.save();
                ctx.scale(root.sizeScale, root.sizeScale);
                ctx.fillStyle = root.bridge.foreground;
                ctx.beginPath();
                if (root.iconName === "media-playback-pause") {
                    ctx.rect(4, 3, 3, 12); ctx.rect(11, 3, 3, 12);
                } else if (root.iconName === "media-skip-backward") {
                    ctx.moveTo(14, 3); ctx.lineTo(5, 9); ctx.lineTo(14, 15); ctx.closePath();
                    ctx.rect(3, 3, 2, 12);
                } else if (root.iconName === "media-skip-forward") {
                    ctx.moveTo(4, 3); ctx.lineTo(13, 9); ctx.lineTo(4, 15); ctx.closePath();
                    ctx.rect(13, 3, 2, 12);
                } else {
                    ctx.moveTo(5, 3); ctx.lineTo(14, 9); ctx.lineTo(5, 15); ctx.closePath();
                }
                ctx.fill();
                ctx.restore();
            }
            Connections {
                target: root
                function onIconNameChanged() { glyph.requestPaint(); }
            }
            Connections {
                target: root.bridge
                function onForegroundChanged() { glyph.requestPaint(); }
            }
        }
    }
    background: Rectangle {
        radius: 5
        color: root.down ? Qt.rgba(root.bridge.accent.r, root.bridge.accent.g, root.bridge.accent.b, 0.3) :
            root.hovered ? Qt.rgba(root.bridge.foreground.r, root.bridge.foreground.g, root.bridge.foreground.b, 0.12) : "transparent"
    }
    QQC.ToolTip.visible: hovered
    QQC.ToolTip.text: text
    onClicked: bridge.command(commandAction)
    Accessible.name: text
}
