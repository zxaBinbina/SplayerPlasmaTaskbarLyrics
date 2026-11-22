.pragma library
.import "LicenseText.js" as LicenseText
// SPDX-License-Identifier: AGPL-3.0-only

function findPageOwner(item) {
    if (!item) return null;
    if (item.hasOwnProperty("currentConfigPage")) return item;
    var children = item.children || [];
    for (var i = 0; i < children.length; i++) {
        var owner = findPageOwner(children[i]);
        if (owner) return owner;
    }
    return null;
}

function bindLicense(contentItem) {
    var owner = findPageOwner(contentItem);
    if (!owner) return false;
    var children = owner.children || [];
    for (var i = 0; i < children.length; i++)
        if (children[i].objectName === "sptlNativeLicenseBinding") return true;

    // KPluginMetaData only supplies texts for KDE's predefined licenses;
    // AGPL is not in that list. AboutPlugin exposes mutable metaData, so supply
    // our packaged license text to that page without changing KDE's files.
    // Parenting the binding to the host page owner keeps its creation context
    // alive when the settings page is replaced by the native About page.
    var code = 'import QtQuick 2.15\nItem {\n' +
        'id: binding; objectName: "sptlNativeLicenseBinding"; visible: false\n' +
        'property string licenseText: ' + JSON.stringify(LicenseText.text) + '\n' +
        'function patch() {\n' +
        ' var page = parent.currentConfigPage;\n' +
        ' if (!page || !page.metaData || page.metaData.pluginId !== "org.kde.plasma.sptl") return;\n' +
        ' if (page.metaData.licenseText === licenseText) return;\n' +
        ' var original = page.metaData; var updated = {};\n' +
        ' var keys = ["pluginId", "iconName", "name", "version", "description", "website", "bugReportUrl", "copyrightText", "license", "authors", "otherContributors", "translators"];\n' +
        ' keys.forEach(function(key) { updated[key] = original[key]; });\n' +
        ' updated.licenseText = licenseText; page.metaData = updated;\n' +
        '}\n' +
        'Connections { target: binding.parent; function onCurrentConfigPageChanged() { Qt.callLater(binding.patch); } }\n' +
        'Component.onCompleted: Qt.callLater(patch)\n' +
        '}';
    Qt.createQmlObject(code, owner, "sptl-native-license-binding");
    return true;
}
