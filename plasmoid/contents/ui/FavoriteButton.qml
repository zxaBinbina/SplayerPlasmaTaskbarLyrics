// SPDX-License-Identifier: AGPL-3.0-only
import QtQuick 2.15

ControlButton {
    iconName: "favorite"
    commandAction: "favorite"
    commandValue: bridge.track ? {id: bridge.track.id, source: bridge.track.source, path: bridge.track.path || ""} : null
    checked: bridge.favoriteLiked
    enabled: bridge.connected && !!bridge.track && bridge.favoriteAvailable
    text: !bridge.favoriteAvailable ? bridge.tr("收藏暂不可用，请检查 SP 托盘", "Favorite unavailable; check the SP tray") :
        bridge.favoriteLiked ? bridge.tr("取消收藏", "Remove favorite") : bridge.tr("收藏", "Favorite")
}
