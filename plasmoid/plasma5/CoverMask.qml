// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtGraphicalEffects 1.15

OpacityMask {
    maskSource: Rectangle {
        width: parent.width
        height: parent.height
        radius: Math.min(width, height) / 2
        color: "white"
    }
}
