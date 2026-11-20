// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15

Item {
    id: root
    width: 0; height: 0
    property var bridge
    property var configuration
    property string lastRequest: ""
    property bool initialized: false
    property var pending: ({})

    function acceptRequest(value) {
        if (!initialized || !value || value === lastRequest) return;
        try {
            var request = JSON.parse(value);
            if (!request.changes || typeof request.changes !== "object") return;
            var next = Object.assign({}, pending, request.changes);
            pending = next;
            lastRequest = value;
            flush();
        } catch (error) { bridge.lastError = bridge.tr("设置格式无效", "Invalid settings"); }
    }
    function flush() {
        if (!Object.keys(pending).length) return;
        var sent = Object.assign({}, pending);
        bridge.saveSettings(sent, function(success) {
            if (!success) return;
            var next = Object.assign({}, pending);
            Object.keys(sent).forEach(function(key) {
                if (next[key] === sent[key]) delete next[key];
            });
            pending = next;
            flush();
        });
    }
    Connections {
        target: root.configuration
        function onValueChanged(key, value) {
            if (key === "settingsRequest") root.acceptRequest(value);
        }
    }
    Timer { interval: 1000; repeat: true; running: Object.keys(root.pending).length > 0; onTriggered: root.flush() }
    Component.onCompleted: {
        // An applet's saved Apply request is history, not its own settings copy.
        // Replaying it at startup would overwrite newer edits from other applets.
        lastRequest = configuration.settingsRequest || "";
        initialized = true;
    }
}
