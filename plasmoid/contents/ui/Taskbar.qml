// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15 as QQC
import "Logic.js" as Logic

Item {
    id: root
    property var bridge
    signal popupRequested()
    readonly property bool hovered: hover.hovered
    readonly property bool collapsed: !bridge.running
    readonly property real panelScale: Math.max(0.01, height / 42)
    readonly property real verticalPadding: collapsed ? 4 * panelScale : Math.max(0,
        Math.min(4 * panelScale, (height - first.implicitHeight - second.implicitHeight) / 2))
    readonly property real coverSize: Math.max(0, height - verticalPadding * 2)
    readonly property real referenceTextHeight: Math.max(1,
        Math.ceil(primaryMeasure.implicitHeight) + Math.ceil(secondaryMeasure.implicitHeight))
    readonly property real primarySize: Math.max(1, Math.floor(Math.min(
        bridge.settings.fontSize * panelScale,
        Math.max(1, height - 2) * bridge.settings.fontSize / referenceTextHeight)))
    readonly property real contentHeight: collapsed ? coverSize : first.implicitHeight + second.implicitHeight
    readonly property var display: Logic.display(bridge.lines, bridge.currentIndex, bridge.track,
        bridge.settings, hovered, bridge.connected ? bridge.tr("未在播放", "Not playing") : bridge.statusText(),
        bridge.tr("未知艺术家", "Unknown artist"))
    readonly property bool showControls: hovered && !collapsed && bridge.connected
    property bool ready: false
    property real controlsProgress: showControls ? 1 : 0
    Behavior on controlsProgress {
        NumberAnimation { id: controlsMotion; duration: bridge.motionDuration; easing.type: Easing.OutCubic }
    }
    readonly property real targetWidth: bridge.hidden ? 0 : collapsed ? coverSize + 8 * panelScale :
        Logic.width(bridge.settings.widthMode, bridge.settings.fixedWidth, bridge.settings.maxWidth,
            Math.max(first.naturalWidth, second.naturalWidth), coverSize, showControls ? 88 * panelScale : 0,
            (showControls ? 24 : 16) * panelScale)
    readonly property real controlScale: Math.min(panelScale,
        Math.max(0.1, (targetWidth - coverSize - 24 * panelScale - 24) / 88))
    property real animatedWidth: targetWidth
    // Enforce a newly lowered maximum even while an earlier resize is running.
    readonly property real layoutWidth: bridge.hidden ? 0 :
        Math.min(animatedWidth, !collapsed && bridge.settings.widthMode === "auto" ? bridge.settings.maxWidth : animatedWidth)
    Behavior on animatedWidth {
        enabled: root.ready && root.visible
        NumberAnimation { id: widthMotion; duration: bridge.motionDuration; easing.type: Easing.OutCubic }
    }
    implicitWidth: layoutWidth
    implicitHeight: 42
    Layout.minimumHeight: 16
    Layout.fillHeight: true
    Layout.minimumWidth: layoutWidth
    Layout.preferredWidth: layoutWidth
    Layout.maximumWidth: layoutWidth
    visible: !bridge.hidden
    clip: true
    Component.onCompleted: ready = true
    // Panel resizing must fit its new height immediately, including buttons.
    onHeightChanged: Qt.callLater(function() { widthMotion.complete(); controlsMotion.complete(); })
    Connections {
        target: bridge
        function onMotionDurationChanged() {
            if (bridge.motionDuration === 0) { widthMotion.complete(); controlsMotion.complete(); }
        }
    }

    function bodyClick() {
        if (collapsed) {
            if (bridge.settings.offlineClick === "launch") bridge.command("launch");
        } else if (bridge.settings.clickAction === "open") bridge.command("open");
        else if (bridge.settings.clickAction === "popup") popupRequested();
    }
    HoverHandler { id: hover }
    WheelHandler {
        onWheel: function(event) {
            if (bridge.connected) {
                var delta = event.angleDelta.y || event.angleDelta.x || event.pixelDelta.y;
                if (delta) bridge.command("volume", (delta > 0 ? 1 : -1) * 0.05);
            }
            event.accepted = true;
        }
    }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 4 * root.panelScale
        anchors.rightMargin: 4 * root.panelScale
        anchors.topMargin: root.verticalPadding
        anchors.bottomMargin: root.verticalPadding
        spacing: 6 * root.panelScale
        layoutDirection: bridge.settings.coverPosition === "right" ? Qt.RightToLeft : Qt.LeftToRight
        Cover {
            source: bridge.coverSource
            idle: !bridge.track
            transitionDuration: bridge.motionDuration
            Layout.preferredWidth: root.coverSize
            Layout.preferredHeight: root.coverSize
            Layout.alignment: Qt.AlignVCenter
            MouseArea { anchors.fill: parent; onClicked: root.bodyClick() }
        }
        Item {
            objectName: "lyricArea"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: lyricColumn.implicitHeight
            Layout.preferredHeight: implicitHeight
            Layout.alignment: Qt.AlignVCenter
            visible: !root.collapsed
            Column {
                id: lyricColumn
                objectName: "lyricColumn"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 0
                Marquee {
                    id: first
                    objectName: "primaryLyric"
                    width: parent.width
                    text: root.display.primary
                    pixelSize: root.primarySize
                    textColor: bridge.foreground
                    highlightColor: bridge.accent
                    words: root.display.words
                    position: bridge.lyricPosition
                    lineActive: !root.hovered && bridge.currentIndex >= 0
                    transitionDuration: bridge.motionDuration
                }
                Marquee {
                    id: second
                    objectName: "secondaryLyric"
                    width: parent.width
                    text: root.display.secondary
                    pixelSize: root.primarySize * 0.82
                    textColor: bridge.secondary
                    highlightColor: bridge.accent
                    words: root.display.secondaryWords || []
                    position: bridge.lyricPosition
                    transitionDuration: bridge.motionDuration
                }
            }
            MouseArea { anchors.fill: parent; onClicked: root.bodyClick() }
        }
        Item {
            visible: root.showControls || root.controlsProgress > 0
            enabled: root.showControls
            clip: true
            opacity: root.controlsProgress
            Layout.preferredWidth: controlsBar.implicitWidth * root.controlsProgress
            Layout.preferredHeight: controlsBar.implicitHeight
            Layout.alignment: Qt.AlignVCenter
            Controls {
                id: controlsBar
                objectName: "taskbarControls"
                bridge: root.bridge
                sizeScale: root.controlScale
                anchors.verticalCenter: parent.verticalCenter
                x: bridge.settings.coverPosition === "right" ? 0 : parent.width - width
            }
        }
    }
    // Measure the configured reference size separately so fitting the rendered
    // font to a resized panel cannot feed back into its own height calculation.
    Text {
        id: primaryMeasure
        visible: false
        text: root.display.primary
        textFormat: Text.PlainText
        font.pixelSize: bridge.settings.fontSize
    }
    Text {
        id: secondaryMeasure
        visible: false
        text: root.display.secondary
        textFormat: Text.PlainText
        font.pixelSize: bridge.settings.fontSize * 0.82
    }
    QQC.ToolTip.visible: hovered && (collapsed || !bridge.connected)
    QQC.ToolTip.text: bridge.statusText()
    Accessible.name: display.primary + " " + display.secondary
    Accessible.role: Accessible.Button
}
