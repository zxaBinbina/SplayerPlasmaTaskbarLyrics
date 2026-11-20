// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import "Logic.js" as Logic

Item {
    id: root
    clip: true
    property string text: ""
    property real pixelSize: 14
    property color textColor: "white"
    property color highlightColor: "#fe7971"
    property var words: []
    property real position: 0
    property bool lineActive: false
    property bool animate: true
    property double epoch: Date.now()
    property double tick: Date.now()
    readonly property real naturalWidth: base.implicitWidth
    readonly property real overflow: Math.max(0, naturalWidth - width)
    readonly property real highlightWidth: {
        var sum = 0;
        for (var i = 0; i < words.length; i++)
            sum += metrics.advanceWidth(words[i].word) * Logic.wordProgress(words[i], position);
        return Math.min(naturalWidth, sum);
    }
    readonly property real offset: {
        if (overflow <= 0) return 0;
        if (words.length > 0) return Math.max(0, Math.min(overflow, highlightWidth - width * 0.6));
        var travel = overflow / 32 * 1000, elapsed = Math.max(0, tick - epoch);
        var phase = elapsed % (travel * 2 + 2400);
        if (phase < 1200) return 0;
        if (phase < travel + 1200) return (phase - 1200) / travel * overflow;
        if (phase < travel + 2400) return overflow;
        return Math.max(0, overflow * (1 - (phase - travel - 2400) / travel));
    }
    implicitHeight: Math.ceil(Math.max(metrics.height, base.implicitHeight))
    FontMetrics { id: metrics; font: base.font }
    Text {
        id: base
        objectName: "renderedText"
        x: -root.offset
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        textFormat: Text.PlainText
        font.pixelSize: root.pixelSize
        color: root.lineActive && !root.words.length ? root.highlightColor : root.textColor
    }
    Item {
        x: -root.offset
        width: root.highlightWidth
        height: parent.height
        clip: true
        visible: root.words.length > 0
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            textFormat: Text.PlainText
            font: base.font
            color: root.highlightColor
        }
    }
    Timer {
        interval: 33
        running: root.visible && root.animate && root.overflow > 0 && root.words.length === 0
        repeat: true
        onTriggered: root.tick = Date.now()
    }
    onTextChanged: { epoch = Date.now(); tick = epoch; }
    onWidthChanged: { epoch = Date.now(); tick = epoch; }
}
