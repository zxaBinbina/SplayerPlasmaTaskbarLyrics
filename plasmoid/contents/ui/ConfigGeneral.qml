// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15 as QQC
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import "Defaults.js" as Defaults
import "ConfigurationHelpers.js" as ConfigurationHelpers

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
    implicitWidth: 680
    implicitHeight: 620
    leftPadding: Kirigami.Units.largeSpacing
    rightPadding: Kirigami.Units.largeSpacing + QQC.ScrollBar.vertical.width
    topPadding: Kirigami.Units.largeSpacing
    bottomPadding: Kirigami.Units.largeSpacing
    contentWidth: availableWidth
    contentHeight: form.implicitHeight
    clip: true
    QQC.ScrollBar.horizontal.policy: QQC.ScrollBar.AlwaysOff
    Bridge { id: configBridge }
    Component.onCompleted: Qt.callLater(function() {
        if (root.Window.window) ConfigurationHelpers.bindLicense(root.Window.window.contentItem);
    })

    function label(value) {
        var parts = value.split(" / ");
        return parts[configBridge.chinese ? 0 : 1] || parts[0];
    }
    function settingsFor(keys) {
        return keys.map(function(key) {
            return Defaults.schema.find(function(setting) { return setting.key === key; });
        });
    }
    function settingLabel(setting) {
        if (setting.key === "fontSize") return configBridge.tr("基准字号", "Reference font size");
        if (setting.key === "manualAccent") return configBridge.tr("手动主题色", "Manual accent");
        return label(setting.label);
    }
    function settingEnabled(key) {
        if (key === "singlePreferAux") return draft.lyricMode === "single";
        if (key === "fixedWidth") return draft.widthMode === "fixed";
        if (key === "maxWidth") return draft.widthMode === "auto";
        if (key === "rotateCover") return draft.coverShape === "circle";
        if (key === "coverRadius") return draft.coverShape === "rounded";
        if (key === "manualDark" || key === "manualAccent") return draft.themeMode === "manual";
        if (key === "offlineClick") return draft.offlineDisplay === "icon";
        return true;
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
        spacing: Kirigami.Units.largeSpacing
        QQC.Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            color: Kirigami.Theme.disabledTextColor
            text: configBridge.tr("在此修改设置后点击“应用”。所有 SPTL 小部件共用这些设置。",
                "Click Apply to save. These settings are shared by all SPTL widgets.")
            wrapMode: Text.Wrap
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !configBridge.reachable
            type: Kirigami.MessageType.Information
            text: configBridge.tr("辅助程序未连接，连接恢复后将同步已应用的设置。",
                "The bridge is unavailable. Applied settings will sync when it reconnects.")
        }
        Kirigami.FormLayout {
            id: settingsForm
            objectName: "settingsForm"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Item {
                Kirigami.FormData.label: configBridge.tr("歌词显示", "Lyrics")
                Kirigami.FormData.isSection: true
            }
            Repeater {
                model: root.settingsFor(["lyricMode", "auxiliary", "singlePreferAux", "fontSize"])
                delegate: settingDelegate
            }
            QQC.Frame {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: Kirigami.Units.gridUnit * 16
                padding: Kirigami.Units.largeSpacing
                ColumnLayout {
                    width: parent.width
                    spacing: Kirigami.Units.smallSpacing
                    QQC.Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: configBridge.tr("字号预览 · 42 像素组件高度", "Font preview · 42px widget height")
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.Wrap
                    }
                    QQC.Label {
                        objectName: "fontPreview"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: configBridge.tr("把今天唱给你听", "Sing today for you")
                        font.pixelSize: root.draft.fontSize
                        wrapMode: Text.Wrap
                    }
                    QQC.Label {
                        Layout.fillWidth: true
                        text: "SPlayer Next"
                        color: Kirigami.Theme.disabledTextColor
                    }
                }
            }
            QQC.Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: Kirigami.Units.gridUnit * 16
                text: configBridge.tr("封面、文字和按钮随任务栏高度缩放；空间不足时，文字会自动缩小以完整显示两行。",
                    "Artwork, text and buttons scale with the panel height. Text shrinks when needed to fit both lines.")
                color: Kirigami.Theme.disabledTextColor
                wrapMode: Text.Wrap
            }
            Kirigami.Separator {
                Kirigami.FormData.label: configBridge.tr("尺寸与布局", "Size and layout")
                Kirigami.FormData.isSection: true
            }
            Repeater {
                model: root.settingsFor(["coverPosition", "coverShape", "coverRadius", "rotateCover", "widthMode", "fixedWidth", "maxWidth"])
                delegate: settingDelegate
            }
            Kirigami.Separator {
                Kirigami.FormData.label: configBridge.tr("主题与动画", "Theme and animations")
                Kirigami.FormData.isSection: true
            }
            Repeater {
                model: root.settingsFor(["themeMode"])
                delegate: settingDelegate
            }
            Kirigami.InlineMessage {
                objectName: "spThemeWarning"
                Layout.fillWidth: true
                visible: root.draft.themeMode === "splayer" && (!configBridge.reachable || !configBridge.theme.available)
                type: Kirigami.MessageType.Warning
                text: configBridge.theme.source === "cover" ?
                    configBridge.tr("无法读取 SPlayer 的封面动态主题色，“跟随 SP”将使用 Plasma 配色。",
                        "SPlayer's dynamic cover color is unavailable. Follow SP will use Plasma colors.") :
                    configBridge.tr("无法读取 SPlayer 当前主题色，“跟随 SP”将使用 Plasma 配色。",
                        "SPlayer's current theme color is unavailable. Follow SP will use Plasma colors.")
            }
            Repeater {
                model: root.settingsFor(["manualDark", "manualAccent", "animationsEnabled"])
                delegate: settingDelegate
            }
            Kirigami.Separator {
                Kirigami.FormData.label: configBridge.tr("交互与离线", "Interaction and offline behavior")
                Kirigami.FormData.isSection: true
            }
            Repeater {
                model: root.settingsFor(["clickAction", "idleClick", "clickLyricSeek", "hoverFavoriteEnabled", "offlineDisplay", "offlineClick"])
                delegate: settingDelegate
            }
        }
        Kirigami.Separator { Layout.fillWidth: true }
        QQC.Button {
            objectName: "restoreDefaults"
            Layout.alignment: Qt.AlignRight
            text: configBridge.tr("恢复默认设置", "Restore defaults")
            onClicked: {
                root.edits = Object.assign({}, Defaults.settings);
                root.cfg_settingsRequest = JSON.stringify({changes: root.edits, nonce: Date.now() + "-" + Math.random()});
            }
        }
    }
    Component {
        id: settingDelegate
        Loader {
            property var setting: modelData
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredWidth: Kirigami.Units.gridUnit * 16
            Kirigami.FormData.label: setting.type === "switch" ? "" : root.settingLabel(setting) + ":"
            Kirigami.FormData.buddyFor: item
            enabled: root.settingEnabled(setting.key)
            sourceComponent: setting.type === "select" ? selectEditor :
                setting.type === "switch" ? switchEditor :
                setting.type === "number" ? numberEditor : colorEditor
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
            text: root.settingLabel(setting)
            checked: root.draft[setting.key]
            onToggled: root.edit(setting.key, checked)
        }
    }
    Component {
        id: numberEditor
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            QQC.SpinBox {
                objectName: "setting_" + setting.key
                Layout.preferredWidth: Kirigami.Units.gridUnit * 7
                from: setting.min; to: setting.max
                value: root.draft[setting.key]
                editable: true
                Accessible.name: root.settingLabel(setting)
                onValueModified: root.edit(setting.key, value)
            }
            QQC.Label {
                text: setting.unit || "px"
                color: Kirigami.Theme.disabledTextColor
            }
            Item { Layout.fillWidth: true }
        }
    }
    Component {
        id: colorEditor
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Rectangle {
                Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                Layout.preferredHeight: Layout.preferredWidth
                radius: Kirigami.Units.smallSpacing
                color: root.draft[setting.key]
                border.width: 1
                border.color: Kirigami.Theme.disabledTextColor
                Accessible.ignored: true
            }
            QQC.TextField {
                objectName: "setting_" + setting.key
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.draft[setting.key]
                placeholderText: "#RRGGBB"
                Accessible.name: root.settingLabel(setting)
                validator: RegularExpressionValidator { regularExpression: /#[0-9a-fA-F]{6}/ }
                onTextEdited: { if (acceptableInput) root.edit(setting.key, text); }
            }
        }
    }
}
