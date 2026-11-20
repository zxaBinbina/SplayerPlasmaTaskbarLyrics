#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Click the real QML controls through the HTTP bridge, including queue paging."""
import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
from sptl.server import BridgeServer
from PySide6.QtCore import QObject, QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest


class Environment:
    running = True
    locale = "zh-CN"
    theme = {"available": True, "mode": "dark", "accent": "#fe7971"}
    favorite = {"available": True, "liked": False}
    favorite_clicks = 0
    def refresh(self): pass
    def local_cover(self, cover): return None
    def toggle_favorite(self):
        self.favorite = dict(available=True, liked=not self.favorite["liked"])
        self.favorite_clicks += 1


def main():
    app = QGuiApplication(sys.argv)
    environment = Environment()
    server = BridgeServer(("127.0.0.1", 0), environment=environment)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    tracks = [dict(id=str(i), source="local", title=f"第 {i+1} 首 · Playlist song", artists=[{"name": "演示歌手"}], path=f"/music/{i}.flac")
              for i in range(72)]
    data = dict(protocol=1, session="controls", lyricRevision=1, lines=[], locale="zh-CN", track=tracks[3],
                playback=dict(state="paused", position=4000, duration=60000, timestamp=0, repeat="list", shuffle="off"),
                modeAvailable=True, queue=dict(available=True, tracks=[], total=0, offset=0, currentIndex=3, requestId=0))
    with server.lock:
        server.state.exchange(data)
    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda entries: warnings.extend(entry.toString() for entry in entries))
    component = QQmlComponent(engine)
    ui = (ROOT / "dist/plasma6/org.kde.plasma.sptl/contents/ui").as_uri()
    component.setData(f"""
import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Layouts 1.15
import "{ui}" as SPTL
Window {{
    id: window
    width: 800; height: 760; visible: true; color: "#131316"
    property int lengthMode: 1
    property int popupCount: 0
    SPTL.Bridge {{ id: testBridge; objectName: "bridge"; endpoint: "http://127.0.0.1:{server.server_address[1]}" }}
    RowLayout {{
        x: 20; y: 20; width: implicitWidth; height: 42
        SPTL.Taskbar {{ objectName: "taskbar"; bridge: testBridge; onPopupRequested: window.popupCount++ }}
    }}
    SPTL.FullLyrics {{ objectName: "popup"; bridge: testBridge; x: 20; y: 100; width: 480; height: 560 }}
}}
""".encode(), QUrl("file:///tmp/sptl-controls.qml"))
    window = component.create()
    assert window, "\n".join(error.toString() for error in component.errors())
    bridge = window.findChild(QObject, "bridge")
    taskbar = window.findChild(QObject, "taskbar")
    popup = window.findChild(QObject, "popup")

    def pump(duration=40):
        deadline = time.monotonic() + duration / 1000
        while time.monotonic() < deadline:
            if server.state.clock() - server.state.last_seen > 0.8:
                with server.lock: server.state.exchange(data)
            app.processEvents()
            time.sleep(0.005)

    def until(predicate, timeout=3500):
        deadline = time.monotonic() + timeout / 1000
        while not predicate() and time.monotonic() < deadline: pump()
        assert predicate(), "control or bridge did not settle"

    def expression(obj, code):
        query = QQmlExpression(engine.rootContext(), obj, code)
        result = query.evaluate()
        assert not query.hasError(), query.error().toString()
        return result[0] if isinstance(result, tuple) else result

    def click(item):
        point = item.mapToScene(QPointF(item.property("width") / 2, item.property("height") / 2))
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
        pump(100)

    def command(action, value=None):
        until(lambda: any(item["action"] == action and (value is None or item["value"] == value) for item in server.state.commands))
        return next(item for item in reversed(server.state.commands)
                    if item["action"] == action and (value is None or item["value"] == value))

    def publish():
        with server.lock:
            data["ack"] = [item["id"] for item in server.state.commands]
            server.state.exchange(data)
        expression(bridge, "revision = -1; poll()")
        pump(100)

    def page(request, offset):
        data["queue"] = dict(available=True, tracks=tracks[offset:offset+50], total=len(tracks),
                             currentIndex=3, offset=offset, requestId=request["id"])
        publish()
        until(lambda: bridge.property("queueResponseId") == request["id"])

    try:
        until(lambda: bridge.property("connected") and bridge.property("favoriteAvailable"))
        QTest.mouseMove(window, QPoint(80, 40))
        pump(300)
        hover_favorite = taskbar.findChild(QObject, "hoverFavoriteButton")
        assert hover_favorite.isVisible()
        assert taskbar.findChild(QObject, "taskbarControls").property("baseWidth") == 118
        window.grabWindow().save(str(ROOT / "artifacts/qml-controls-hover.png"))
        click(hover_favorite)
        until(lambda: environment.favorite_clicks == 1)
        until(lambda: bridge.property("favoriteLiked"))
        assert window.property("popupCount") == 0, "favorite clicks must not open the body popup"

        with server.lock: server.update_settings({"hoverFavoriteEnabled": False})
        expression(bridge, "revision = -1; poll()")
        until(lambda: not hover_favorite.isVisible())
        assert taskbar.findChild(QObject, "taskbarControls").property("baseWidth") == 88
        popup_favorite = popup.findChild(QObject, "popupFavoriteButton")
        assert popup_favorite.isVisible(), "hover setting must leave the popup favorite available"
        assert popup_favorite.property("checked")
        click(popup_favorite)
        until(lambda: environment.favorite_clicks == 2)
        until(lambda: not bridge.property("favoriteLiked"))

        mode_button = popup.findChild(QObject, "playbackModeButton")
        for mode in ("one", "shuffle", "list"):
            click(mode_button)
            item = popup.findChild(QObject, "mode_" + mode)
            until(lambda: item.isVisible())
            click(item)
            command("mode", mode)
            data["playback"].update(repeat="one" if mode == "one" else "list", shuffle="on" if mode == "shuffle" else "off")
            publish()
            until(lambda: popup.property("playbackMode") == mode)
        window.grabWindow().save(str(ROOT / "artifacts/qml-controls-popup.png"))

        playlist_button = popup.findChild(QObject, "playlistButton")
        click(playlist_button)
        assert popup.property("playlistShown")
        assert not popup.findChild(QObject, "fullLyricsList").isVisible()
        request = command("queue", -1)
        page(request, 0)
        queue_list = popup.findChild(QObject, "playbackQueueList")
        assert queue_list.property("count") == 50
        expression(queue_list, "contentY = 150")
        scroll = queue_list.property("contentY")
        data["queue"]["requestId"] += 100
        publish()
        assert queue_list.property("contentY") == scroll, "background refresh must preserve user scrolling"

        click(popup.findChild(QObject, "nextQueuePage"))
        page(command("queue", 50), 50)
        assert queue_list.property("count") == 22
        until(lambda: expression(queue_list, "itemAtIndex(0)") is not None)
        row = expression(queue_list, "itemAtIndex(0)")
        click(row)
        selected = command("queuePlay")["value"]
        assert selected == {"index": 50, "id": "50", "source": "local", "path": "/music/50.flac"}
        publish()
        window.grabWindow().save(str(ROOT / "artifacts/qml-controls-playlist.png"))

        click(popup.findChild(QObject, "previousQueuePage"))
        page(command("queue", 0), 0)
        click(playlist_button)
        assert not popup.property("playlistShown")
        assert popup.findChild(QObject, "fullLyricsList").isVisible()
        popup.setProperty("width", 320)
        pump(100)
        for name in ("playbackModeButton", "popupControls", "popupFavoriteButton", "playlistButton"):
            button = popup.findChild(QObject, name)
            left = button.mapToScene(QPointF(0, 0)).x()
            right = button.mapToScene(QPointF(button.property("width"), 0)).x()
            assert 36 <= left <= right <= 324, f"{name} must fit a 320px popup"
        window.grabWindow().save(str(ROOT / "artifacts/qml-controls-narrow.png"))
        assert not warnings, "\n".join(warnings)
        print("QML favorite state, hover setting, mode menu, playlist paging/selection and narrow popup checks passed")
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == "__main__":
    main()
