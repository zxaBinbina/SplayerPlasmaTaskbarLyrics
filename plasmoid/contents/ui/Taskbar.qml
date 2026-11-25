// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15 as QQC
import "Logic.js" as Logic

Item {
    id: root
    property var bridge
    readonly property var panelWindow: Window.window
    // PanelView::LengthMode: FillAvailable = 0, FitContent = 1, Custom = 2.
    // Older Plasma and desktop hosts without this property use the normal motion.
    readonly property bool fitContentPanel: panelWindow !== null &&
        typeof panelWindow.lengthMode === "number" && panelWindow.lengthMode === 1
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
    readonly property bool controlsAvailable: bridge.connected && !!bridge.track &&
        (bridge.playing || bridge.playback.state === "paused")
    readonly property bool showControls: hovered && !collapsed && controlsAvailable
    property bool ready: false
    property real controlsProgress: showControls ? 1 : 0
    Behavior on controlsProgress {
        NumberAnimation { id: controlsMotion; duration: bridge.motionDuration; easing.type: Easing.OutCubic }
    }
    readonly property real targetWidth: bridge.hidden ? 0 : collapsed ? coverSize + 8 * panelScale :
        Logic.width(bridge.settings.widthMode, bridge.settings.fixedWidth, bridge.settings.maxWidth,
            Math.max(first.naturalWidth, second.naturalWidth), coverSize, showControls ? controlsBar.baseWidth * panelScale : 0,
            (showControls ? 24 : 16) * panelScale)
    readonly property real controlScale: Math.min(panelScale,
        Math.max(0.1, (targetWidth - coverSize - 24 * panelScale - 24) / controlsBar.baseWidth))
    property real animatedWidth: 0
    property real reservedWidth: 0
    readonly property real widthLimit: !collapsed && bridge.settings.widthMode === "auto" ? bridge.settings.maxWidth : Infinity
    readonly property real visualWidth: bridge.hidden ? 0 : Math.min(animatedWidth, widthLimit)
    // Plasma's fit-content panel resizes its window whenever these hints change.
    // Only that mode reserves space once; content uses the full reserved slot.
    // Other panels keep the original animation of the widget's layout width.
    readonly property real layoutWidth: bridge.hidden ? 0 :
        fitContentPanel ? Math.min(reservedWidth, widthLimit) : visualWidth
    NumberAnimation {
        id: widthMotion
        target: root; property: "animatedWidth"
        duration: bridge.motionDuration; easing.type: Easing.OutCubic
        onFinished: root.reservedWidth = root.targetWidth
    }
    function resize(immediate) {
        if (!ready) return;
        widthMotion.stop();
        var previous = visualWidth;
        if (immediate || !visible || bridge.motionDuration === 0 || Math.abs(targetWidth - previous) < 1) {
            reservedWidth = targetWidth;
            animatedWidth = targetWidth;
            return;
        }
        reservedWidth = Math.min(widthLimit, Math.max(layoutWidth, targetWidth));
        widthMotion.from = previous;
        widthMotion.to = targetWidth;
        widthMotion.start();
    }
    // Both lyric rows may change together. Publish their final size once.
    onTargetWidthChanged: { if (ready) Qt.callLater(resize); }
    onFitContentPanelChanged: resize(true)
    implicitWidth: layoutWidth
    implicitHeight: 42
    Layout.minimumHeight: 16
    Layout.fillHeight: true
    Layout.minimumWidth: layoutWidth
    Layout.preferredWidth: layoutWidth
    Layout.maximumWidth: layoutWidth
    visible: !bridge.hidden
    clip: true
    Component.onCompleted: { ready = true; resize(true); }
    // Panel resizing must fit its new height immediately, including buttons.
    onHeightChanged: Qt.callLater(function() { root.resize(true); controlsMotion.complete(); })
    Connections {
        target: bridge
        function onPlaybackChanged() { root.reconcileVolume(); }
        function onConnectedChanged() {
            if (!bridge.connected) { volumeFeedback.stop(); root.predictedVolume = -1; }
        }
        function onMotionDurationChanged() {
            if (bridge.motionDuration === 0) { root.resize(true); controlsMotion.complete(); }
        }
    }

    function bodyClick() {
        if (collapsed && bridge.settings.offlineClick === "none") return;
        if (collapsed || !bridge.track) {
            if (bridge.settings.idleClick === "liked") bridge.command("startLiked");
            else bridge.command("open");
        } else if (bridge.settings.clickAction === "open") bridge.command("open");
        else if (bridge.settings.clickAction === "popup") popupRequested();
    }
    property real predictedVolume: -1
    function reconcileVolume() {
        // Old snapshots must not pull the OSD backwards during a scroll burst
        // or while an absolute volume command is still awaiting SP's ack.
        if (!bridge.connected || predictedVolume < 0 || volumeFeedback.running || bridge.pendingVolume !== null) return;
        if (Math.abs(predictedVolume - bridge.playback.volume) > 0.000001)
            bridge.command("volumeOsd");
        predictedVolume = -1;
    }
    Timer {
        id: volumeFeedback
        interval: 1500
        onTriggered: root.reconcileVolume()
    }
    HoverHandler { id: hover }
    WheelHandler {
        target: null
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function(event) {
            if (bridge.connected) {
                var delta = event.angleDelta.y || event.angleDelta.x || event.pixelDelta.y || event.pixelDelta.x;
                if (delta) {
                    var base = root.predictedVolume >= 0 ? root.predictedVolume :
                        bridge.pendingVolume !== null ? bridge.pendingVolume : bridge.playback.volume;
                    root.predictedVolume = Math.max(0, Math.min(1, base + (delta > 0 ? 0.05 : -0.05)));
                    volumeFeedback.restart();
                    // Send once per wheel event; OSD and playback use one target.
                    bridge.command("setVolume", root.predictedVolume, true);
                }
            }
            event.accepted = true;
        }
    }
    RowLayout {
        objectName: "taskbarContent"
        anchors.fill: parent
        anchors.leftMargin: 4 * root.panelScale
        anchors.rightMargin: 4 * root.panelScale
        anchors.topMargin: root.verticalPadding
        anchors.bottomMargin: root.verticalPadding
        spacing: 6 * root.panelScale
        layoutDirection: bridge.settings.coverPosition === "right" ? Qt.RightToLeft : Qt.LeftToRight
        Cover {
            objectName: "taskbarCover"
            source: bridge.coverSource
            idle: !bridge.track
            circular: bridge.settings.coverShape === "circle"
            cornerRounding: bridge.settings.coverShape === "rounded" ? bridge.settings.coverRadius / 100 : 0
            rotateWhilePlaying: bridge.settings.rotateCover === true
            playing: bridge.playing
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
            visible: root.controlsAvailable && (root.showControls || root.controlsProgress > 0)
            enabled: root.showControls
            clip: true
            opacity: root.controlsProgress
            // Fit-content panels already reserved this space. Keep all buttons
            // at the slot edge while fading, instead of squeezing the lyric row.
            Layout.minimumWidth: root.fitContentPanel ? Math.ceil(controlsBar.implicitWidth) : 0
            Layout.preferredWidth: root.fitContentPanel ? Math.ceil(controlsBar.implicitWidth) : controlsBar.implicitWidth * root.controlsProgress
            Layout.preferredHeight: controlsBar.implicitHeight
            Layout.alignment: Qt.AlignVCenter
            Controls {
                id: controlsBar
                objectName: "taskbarControls"
                toolTipsEnabled: false
                bridge: root.bridge
                sizeScale: root.controlScale
                showFavorite: bridge.settings.hoverFavoriteEnabled !== false
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
