// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
Item {
    id: root
    property string source: ""
    property bool idle: false
    Image {
        anchors.fill: parent
        source: root.idle ? "../images/splayer.svg" : "../images/placeholder.svg"
        fillMode: Image.PreserveAspectFit
    }
    Image {
        anchors.fill: parent
        source: root.source
        asynchronous: true
        cache: true
        fillMode: Image.PreserveAspectCrop
        visible: status === Image.Ready
    }
}
