// SPDX-License-Identifier: AGPL-3.0-only
import org.kde.plasma.configuration 2.0
import QtQuick 2.15
import "../ui" as SPTL

ConfigModel {
    property Item languageBridge: SPTL.Bridge {}
    ConfigCategory {
        name: languageBridge.tr("设置", "Settings")
        icon: "preferences-other"
        source: "ConfigGeneral.qml"
    }
}
