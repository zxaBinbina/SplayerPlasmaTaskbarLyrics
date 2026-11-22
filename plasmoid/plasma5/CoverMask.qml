// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtGraphicalEffects 1.15

OpacityMask {
    id: effect
    property real radiusFraction: 0.5
    maskSource: Rectangle {
        width: effect.width
        height: effect.height
        radius: Math.min(width, height) * effect.radiusFraction
        color: "white"
    }
}
