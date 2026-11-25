// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC

QQC.ToolButton {
    id: root
    property var bridge
    property real sizeScale: 1
    property string iconName: ""
    property string commandAction: ""
    property string feedbackAction: commandAction
    property var commandValue
    property bool toolTipEnabled: true
    readonly property bool requestPending: feedbackAction !== "" && typeof bridge.actionPending === "function" && bridge.actionPending(feedbackAction)
    readonly property color glyphColor: checked || requestPending ? bridge.accent : bridge.foreground
    implicitWidth: 28 * sizeScale
    implicitHeight: 28 * sizeScale
    hoverEnabled: true
    enabled: bridge.connected && !!bridge.track
    contentItem: Item {
        scale: root.down ? 0.88 : root.hovered ? 1.08 : 1
        Behavior on scale {
            NumberAnimation { id: pressMotion; duration: root.bridge.quickDuration; easing.type: Easing.OutCubic }
        }
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
                ctx.fillStyle = root.glyphColor;
                ctx.strokeStyle = root.glyphColor;
                ctx.lineWidth = 1.6;
                ctx.lineCap = "round";
                ctx.lineJoin = "round";
                var fillGlyph = true;
                ctx.beginPath();
                if (root.iconName === "media-playback-pause") {
                    ctx.rect(4, 3, 3, 12); ctx.rect(11, 3, 3, 12);
                } else if (root.iconName === "media-skip-backward") {
                    ctx.moveTo(14, 3); ctx.lineTo(5, 9); ctx.lineTo(14, 15); ctx.closePath();
                    ctx.rect(3, 3, 2, 12);
                } else if (root.iconName === "media-skip-forward") {
                    ctx.moveTo(4, 3); ctx.lineTo(13, 9); ctx.lineTo(4, 15); ctx.closePath();
                    ctx.rect(13, 3, 2, 12);
                } else if (root.iconName === "favorite" || root.iconName === "dislike") {
                    ctx.moveTo(9, 15);
                    ctx.bezierCurveTo(7, 13, 2, 9.5, 2, 6);
                    ctx.bezierCurveTo(2, 1.5, 7, 1.5, 9, 5);
                    ctx.bezierCurveTo(11, 1.5, 16, 1.5, 16, 6);
                    ctx.bezierCurveTo(16, 9.5, 11, 13, 9, 15);
                    ctx.closePath();
                    if (root.iconName === "dislike") { ctx.moveTo(2, 2); ctx.lineTo(16, 16); }
                    fillGlyph = root.iconName === "favorite" && root.checked;
                } else if (root.iconName === "playlist") {
                    ctx.moveTo(2, 4); ctx.lineTo(15, 4);
                    ctx.moveTo(2, 8); ctx.lineTo(11, 8);
                    ctx.moveTo(2, 12); ctx.lineTo(9, 12);
                    ctx.moveTo(13, 9); ctx.lineTo(17, 12); ctx.lineTo(13, 15); ctx.closePath();
                    fillGlyph = false;
                } else if (root.iconName === "shuffle") {
                    ctx.moveTo(2, 4); ctx.lineTo(5, 4); ctx.lineTo(12, 14); ctx.lineTo(16, 14);
                    ctx.moveTo(2, 14); ctx.lineTo(5, 14); ctx.lineTo(12, 4); ctx.lineTo(16, 4);
                    ctx.moveTo(13.5, 1.5); ctx.lineTo(16, 4); ctx.lineTo(13.5, 6.5);
                    ctx.moveTo(13.5, 11.5); ctx.lineTo(16, 14); ctx.lineTo(13.5, 16.5);
                    fillGlyph = false;
                } else if (root.iconName === "repeat" || root.iconName === "repeat-one") {
                    ctx.moveTo(4, 4); ctx.lineTo(13, 4); ctx.quadraticCurveTo(16, 4, 16, 8);
                    ctx.moveTo(11, 1.5); ctx.lineTo(13.5, 4); ctx.lineTo(11, 6.5);
                    ctx.moveTo(14, 14); ctx.lineTo(5, 14); ctx.quadraticCurveTo(2, 14, 2, 10);
                    ctx.moveTo(7, 11.5); ctx.lineTo(4.5, 14); ctx.lineTo(7, 16.5);
                    if (root.iconName === "repeat-one") {
                        ctx.font = "bold 9px sans-serif";
                        ctx.textAlign = "center";
                        ctx.fillText("1", 9, 12);
                    }
                    fillGlyph = false;
                } else {
                    ctx.moveTo(5, 3); ctx.lineTo(14, 9); ctx.lineTo(5, 15); ctx.closePath();
                }
                if (fillGlyph) ctx.fill(); else ctx.stroke();
                ctx.restore();
            }
            Connections {
                target: root
                function onIconNameChanged() { glyph.requestPaint(); }
                function onGlyphColorChanged() { glyph.requestPaint(); }
                function onCheckedChanged() { glyph.requestPaint(); }
            }
            Connections {
                target: root.bridge
                function onForegroundChanged() { glyph.requestPaint(); }
            }
        }
    }
    background: Rectangle {
        radius: 5
        color: root.down || root.requestPending ? Qt.rgba(root.bridge.accent.r, root.bridge.accent.g, root.bridge.accent.b, 0.3) :
            root.hovered ? Qt.rgba(root.bridge.foreground.r, root.bridge.foreground.g, root.bridge.foreground.b, 0.12) : "transparent"
        Behavior on color { ColorAnimation { id: hoverMotion; duration: root.bridge.quickDuration } }
    }
    Connections {
        target: root.bridge
        function onQuickDurationChanged() {
            if (root.bridge.quickDuration === 0) { pressMotion.complete(); hoverMotion.complete(); }
        }
    }
    QQC.ToolTip.visible: root.toolTipEnabled && hovered
    QQC.ToolTip.text: text
    onClicked: { if (commandAction) bridge.command(commandAction, commandValue); }
    Accessible.name: text
}
