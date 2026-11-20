// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.plasmoid 2.0

PlasmoidItem {
    id: shell
    property real widthHint: 48
    Layout.minimumWidth: widthHint
    Layout.preferredWidth: widthHint
    Layout.maximumWidth: widthHint
    Layout.minimumHeight: 16
    Layout.fillHeight: true
    visible: !sharedBridge.hidden
    Plasmoid.icon: Qt.resolvedUrl("../images/splayer.svg")
    Plasmoid.status: sharedBridge.hidden ? PlasmaCore.Types.HiddenStatus : PlasmaCore.Types.ActiveStatus
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.constraintHints: Plasmoid.CanFillArea
    Bridge { id: sharedBridge }
    SettingsSync { bridge: sharedBridge; configuration: Plasmoid.configuration }

    preferredRepresentation: compactRepresentation
    compactRepresentation: Taskbar {
        bridge: sharedBridge
        onLayoutWidthChanged: shell.widthHint = layoutWidth
        Component.onCompleted: shell.widthHint = layoutWidth
        onPopupRequested: shell.expanded = !shell.expanded
    }
    fullRepresentation: FullLyrics { bridge: sharedBridge }
}
