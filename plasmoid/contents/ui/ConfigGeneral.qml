// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC
import QtQuick.Layouts 1.15
import "Defaults.js" as Defaults

QQC.ScrollView {
    id: root
    property string title: ""
    property string cfg_settingsRequest: ""
    // Plasma passes default metadata and its own panel layout fields too.
    property string cfg_settingsRequestDefault: ""
    property int cfg_length: 0
    property bool cfg_expanding: false
    property alias endpoint: configBridge.endpoint
    property var edits: ({})
    readonly property var draft: Object.assign({}, configBridge.settings, edits)
    implicitWidth: 620
    implicitHeight: 620
    contentWidth: availableWidth
    contentHeight: form.implicitHeight
    clip: true
    QQC.ScrollBar.horizontal.policy: QQC.ScrollBar.AlwaysOff
    Bridge { id: configBridge }

    function label(value) {
        var parts = value.split(" / ");
        return parts[configBridge.chinese ? 0 : 1] || parts[0];
    }
    function edit(key, value) {
        var next = Object.assign({}, edits);
        next[key] = value;
        edits = next;
        cfg_settingsRequest = JSON.stringify({changes: next, nonce: Date.now() + "-" + Math.random()});
    }
    Connections {
        target: configBridge
        function onSettingsChanged() {
            var next = Object.assign({}, root.edits);
            Object.keys(next).forEach(function(key) {
                if (configBridge.settings[key] === next[key]) delete next[key];
            });
            root.edits = next;
        }
    }
    ColumnLayout {
        id: form
        width: root.availableWidth
        spacing: 12
        QQC.Label {
            Layout.fillWidth: true
            text: configBridge.tr("在此修改设置后点击“应用”。所有 SPTL 小部件共用这些设置。",
                "Click Apply to save. These settings are shared by all SPTL widgets.")
            wrapMode: Text.Wrap
        }
        QQC.Label {
            Layout.fillWidth: true
            visible: !configBridge.reachable
            text: configBridge.tr("辅助程序未连接，连接恢复后将同步已应用的设置。",
                "The bridge is unavailable. Applied settings will sync when it reconnects.")
            wrapMode: Text.Wrap
        }
        Repeater {
            model: Defaults.schema
            delegate: RowLayout {
                id: settingRow
                property var setting: modelData
                Layout.fillWidth: true
                QQC.Label {
                    Layout.preferredWidth: 210
                    Layout.fillWidth: true
                    text: root.label(settingRow.setting.label)
                    wrapMode: Text.Wrap
                }
                Loader {
                    Layout.preferredWidth: 260
                    sourceComponent: settingRow.setting.type === "select" ? selectEditor :
                        settingRow.setting.type === "switch" ? switchEditor :
                        settingRow.setting.type === "number" ? numberEditor : colorEditor
                    property var setting: settingRow.setting
                }
            }
        }
        QQC.Label {
            Layout.fillWidth: true
            text: configBridge.tr("封面、文字和按钮随任务栏高度自动缩放。字号为组件高 42 像素时的基准；空间不足时自动缩小，保持两行完整显示。",
                "Artwork, text and buttons scale with the panel height. Font size is the reference at a widget height of 42px; text shrinks when needed to fit both lines.")
            wrapMode: Text.Wrap
        }
        QQC.Label {
            objectName: "fontPreview"
            Layout.fillWidth: true
            text: configBridge.tr("基准字号预览 · SPlayer Next", "Reference font preview · SPlayer Next")
            font.pixelSize: root.draft.fontSize
            wrapMode: Text.Wrap
        }
        QQC.Button {
            text: configBridge.tr("恢复默认设置", "Restore defaults")
            onClicked: {
                root.edits = Object.assign({}, Defaults.settings);
                root.cfg_settingsRequest = JSON.stringify({changes: root.edits, nonce: Date.now() + "-" + Math.random()});
            }
        }
    }
    Component {
        id: selectEditor
        QQC.ComboBox {
            objectName: "setting_" + setting.key
            model: setting.options.map(function(option) { return root.label(option.label); })
            currentIndex: {
                for (var i = 0; i < setting.options.length; i++)
                    if (setting.options[i].value === root.draft[setting.key]) return i;
                return 0;
            }
            onActivated: root.edit(setting.key, setting.options[currentIndex].value)
        }
    }
    Component {
        id: switchEditor
        QQC.CheckBox {
            objectName: "setting_" + setting.key
            checked: root.draft[setting.key]
            onToggled: root.edit(setting.key, checked)
        }
    }
    Component {
        id: numberEditor
        QQC.SpinBox {
            objectName: "setting_" + setting.key
            from: setting.min; to: setting.max
            value: root.draft[setting.key]
            editable: true
            onValueModified: root.edit(setting.key, value)
        }
    }
    Component {
        id: colorEditor
        QQC.TextField {
            objectName: "setting_" + setting.key
            text: root.draft[setting.key]
            placeholderText: "#RRGGBB"
            validator: RegularExpressionValidator { regularExpression: /#[0-9a-fA-F]{6}/ }
            onTextEdited: { if (acceptableInput) root.edit(setting.key, text); }
        }
    }
}
