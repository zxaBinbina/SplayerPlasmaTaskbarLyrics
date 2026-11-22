// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Effects

MultiEffect {
    id: effect
    property real radiusFraction: 0.5
    maskEnabled: true
    maskSource: circleMask
    maskThresholdMin: 0.5
    maskSpreadAtMin: 1
    Rectangle {
        id: circleMask
        anchors.fill: parent
        radius: Math.min(width, height) * effect.radiusFraction
        color: "white"
        visible: false
        layer.enabled: true
    }
}
