// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
Item {
    id: root
    property string source: ""
    property bool idle: false
    property bool circular: false
    property bool rotateWhilePlaying: false
    property bool playing: false
    readonly property bool roundArtwork: circular && !idle
    readonly property real artworkRotation: artwork.rotation
    property int transitionDuration: 0
    property bool ready: false
    property int activeSlot: -1
    property int pendingSlot: -1
    readonly property bool loading: pendingSlot >= 0

    function load() {
        if (!ready) return;
        pendingSlot = activeSlot === 0 ? 1 : 0;
        var slot = pendingSlot;
        var image = slot === 0 ? first : second;
        // The spare slot may still be fading out after a rapid song change.
        // Finish that fade before reusing it for the next asynchronous load.
        if (pendingSlot === 0) firstFade.complete();
        else secondFade.complete();
        image.source = idle ? "../images/splayer.svg" : source;
        loaded(slot, image.status);
    }
    function loaded(slot, status) {
        if (slot < 0 || slot !== pendingSlot) return;
        if (status === Image.Ready) {
            activeSlot = slot;
            pendingSlot = -1;
        } else if (status === Image.Error || status === Image.Null) {
            activeSlot = -1;
            pendingSlot = -1;
        }
    }
    onSourceChanged: load()
    onIdleChanged: load()
    onTransitionDurationChanged: {
        if (ready && transitionDuration === 0) { firstFade.complete(); secondFade.complete(); }
    }
    Component.onCompleted: { ready = true; load(); }
    Item {
        id: artwork
        anchors.fill: parent
        layer.enabled: root.roundArtwork
        layer.effect: CoverMask {}
        NumberAnimation on rotation {
            objectName: "coverRotation"
            from: 0; to: 360; duration: 20000; loops: Animation.Infinite
            running: root.roundArtwork && root.rotateWhilePlaying && root.visible
            paused: running && !root.playing
            onRunningChanged: { if (!running) artwork.rotation = 0; }
        }
        Image {
            anchors.fill: parent
            source: root.idle ? "../images/splayer.svg" : "../images/placeholder.svg"
            fillMode: Image.PreserveAspectFit
        }
        Image {
            id: first
            objectName: "coverFirst"
            z: root.activeSlot === 0 ? 2 : 1
            anchors.fill: parent
            asynchronous: true
            cache: true
            fillMode: Image.PreserveAspectCrop
            opacity: root.activeSlot === 0 ? 1 : 0
            visible: opacity > 0 && status === Image.Ready
            onStatusChanged: root.loaded(0, status)
            Behavior on opacity {
                NumberAnimation { id: firstFade; duration: root.transitionDuration; easing.type: Easing.OutCubic }
            }
        }
        Image {
            id: second
            objectName: "coverSecond"
            z: root.activeSlot === 1 ? 2 : 1
            anchors.fill: parent
            asynchronous: true
            cache: true
            fillMode: Image.PreserveAspectCrop
            opacity: root.activeSlot === 1 ? 1 : 0
            visible: opacity > 0 && status === Image.Ready
            onStatusChanged: root.loaded(1, status)
            Behavior on opacity {
                NumberAnimation { id: secondFade; duration: root.transitionDuration; easing.type: Easing.OutCubic }
            }
        }
    }
}
