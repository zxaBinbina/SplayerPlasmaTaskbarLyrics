#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Load the actual shared Plasma 6 UI, exercise sync/layout, and render an artifact."""
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
from sptl.model import DEFAULTS
from sptl.server import BridgeServer

from PySide6.QtCore import QObject, QUrl, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QWheelEvent, QPointingDevice, QInputDevice
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, QQmlPropertyMap
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest


class FakeEnvironment:
    running = False
    locale = None
    theme = {"available": True, "mode": "dark", "accent": "#fe7971"}
    def refresh(self): pass
    def local_cover(self, cover): return None
    launched = 0
    def activate(self): self.launched += 1
    def __init__(self): self.volume_osds = []
    def show_volume(self, percent): self.volume_osds.append(percent)


def main():
    server = BridgeServer(("127.0.0.1", 0), environment=FakeEnvironment())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    app = QGuiApplication(sys.argv)
    QIcon.setThemeName("breeze")
    engine = QQmlEngine()
    configuration = QQmlPropertyMap()
    configuration.insert("settingsRequest", "")
    engine.rootContext().setContextProperty("testConfiguration", configuration)
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
    component = QQmlComponent(engine)
    ui = (ROOT / "dist/plasma6/org.kde.plasma.sptl/contents/ui").as_uri()
    port = server.server_address[1]
    component.setData(f"""
import QtQuick 2.15
import QtQuick.Window 2.15
import "{ui}" as SPTL
Window {{
    id: testWindow
    property int popupCount: 0
    width: 960; height: 680; visible: true; color: "#131316"
    SPTL.Bridge {{ id: testBridge; objectName: "bridge"; endpoint: "http://127.0.0.1:{port}" }}
    SPTL.Bridge {{ id: secondBridge; endpoint: "http://127.0.0.1:{port}" }}
    SPTL.SettingsSync {{ objectName: "settingsSync"; bridge: testBridge; configuration: testConfiguration }}
    SPTL.Taskbar {{
        objectName: "panel"; x: 20; y: 20; width: implicitWidth; height: 48
        bridge: testBridge
        onPopupRequested: testWindow.popupCount++
    }}
    SPTL.FullLyrics {{
        objectName: "popup"; x: 20; y: 88; width: 480; height: 560; bridge: testBridge
    }}
    SPTL.Taskbar {{
        objectName: "secondPanel"; x: 520; y: 20; width: implicitWidth; height: 48
        bridge: secondBridge
    }}
}}
""".encode(), QUrl("file:///tmp/sptl-smoke.qml"))
    if component.status() == QQmlComponent.Error:
        raise AssertionError("\n".join(e.toString() for e in component.errors()))
    window = component.create()
    if not window:
        raise AssertionError("\n".join(e.toString() for e in component.errors()))
    bridge = window.findChild(QObject, "bridge")
    panel = window.findChild(QObject, "panel")
    second = window.findChild(QObject, "secondPanel")
    def pump(duration=650):
        deadline = time.monotonic() + duration / 1000
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
    def expression(obj, source):
        value = QQmlExpression(engine.rootContext(), obj, source)
        result = value.evaluate()
        if value.hasError():
            raise AssertionError(value.error().toString())
        return result[0] if isinstance(result, tuple) else result
    def visual_find(item, name):
        # Traverse in QML: PySide cannot wrap some private Kirigami item types.
        return expression(item, """
            (function find(item, name) {
                if (item.objectName === name) return item;
                for (var i = 0; i < item.children.length; i++) {
                    var found = find(item.children[i], name);
                    if (found) return found;
                }
                return null;
            })(this, %s)
        """ % json.dumps(name))
    data = {
        "protocol": 1, "session": "qml", "lyricRevision": 1,
        "settings": dict(DEFAULTS, maxWidth=340), "locale": "zh-CN",
        "track": {"id":"demo", "source":"local",
                  "title":"一首很长的歌曲名称 · A very long song title for marquee verification",
                  "artists":[{"name":"演示歌手 / Demonstration artist with a long name"}], "duration":120000},
        "lines":[
            {"startTime":0,"endTime":5000,"words":[{"word":"把今天", "startTime":0,"endTime":2000},
             {"word":"唱给你听，这是一句需要随演唱位置滚动的长歌词","startTime":2000,"endTime":5000}],
             "translatedLyric":"Sing today for you — a translation that scrolls when space runs out",
             "romanLyric":"Ba jin tian chang gei ni ting"},
            {"startTime":5000,"endTime":12000,"words":[{"word":"下一句也会继续同步","startTime":5000,"endTime":12000}],
             "translatedLyric":"The next line stays in sync"},
            {"startTime":12000,"endTime":18000,"words":[{"word":"没有翻译时显示下一句","startTime":12000,"endTime":18000}]}
        ],
        "playback":{"state":"paused","position":2600,"duration":120000,"speed":1,"offset":0,"timestamp":int(time.time()*1000)}
    }
    def publish():
        server.update_settings(data["settings"])
        server.state.exchange(data)
    settings_window = None
    try:
        with server.lock:
            publish()
        pump()
        assert bridge.property("connected") is True, str(errors) + str(expression(bridge, "JSON.stringify(content)"))
        assert bridge.property("currentIndex") == 0
        assert panel.property("targetWidth") <= 340
        assert panel.property("targetWidth") == second.property("targetWidth")
        assert panel.findChild(QObject, "lyricArea").property("height") > 25
        primary = panel.findChild(QObject, "primaryLyric")
        secondary = panel.findChild(QObject, "secondaryLyric")
        for font_size in (9, 14, 24, 32):
            with server.lock:
                data["settings"] = dict(data["settings"], fontSize=font_size)
                publish()
            pump()
            previous_cover, previous_font = 0, 0
            for panel_height in (20, 24, 32, 42, 46, 64, 84, 120, 42):
                panel.setProperty("height", panel_height)
                pump(80)
                origin = panel.mapToScene(QPointF(0, 0)).y()
                first_text = primary.findChild(QObject, "renderedText")
                second_text = secondary.findChild(QObject, "renderedText")
                top = first_text.mapToScene(QPointF(0, 0)).y() - origin
                bottom = second_text.mapToScene(QPointF(0, second_text.property("height"))).y() - origin
                assert top >= 0, (panel_height, font_size, top)
                assert bottom <= panel_height, (panel_height, font_size, bottom)
                assert abs((top + bottom) / 2 - panel_height / 2) < 1, (panel_height, font_size, top, bottom)
                cover_size = panel.property("coverSize")
                rendered_font = panel.property("primarySize")
                assert cover_size <= panel_height
                assert panel.property("targetWidth") <= 340
                assert panel.property("implicitHeight") == 42, "resizing must not change the requested panel height"
                if panel_height != 42 or previous_cover < 42:
                    assert cover_size >= previous_cover
                    assert rendered_font >= previous_font
                previous_cover, previous_font = cover_size, rendered_font
            assert cover_size < 42, "returning to a small panel must shrink the artwork"
        panel.setProperty("height", 42)
        second.setProperty("height", 42)
        previous_width = 0
        for font_size in (9, 14):
            with server.lock:
                data["settings"] = dict(data["settings"], fontSize=font_size)
                publish()
            pump()
            assert panel.property("primarySize") == font_size
            assert expression(primary.findChild(QObject, "renderedText"), "font.pixelSize") == font_size
            assert abs(secondary.property("pixelSize") - font_size * 0.82) < 0.001
            assert primary.property("naturalWidth") > previous_width
            previous_width = primary.property("naturalWidth")
            assert second.property("primarySize") == font_size
            assert panel.property("contentHeight") <= 42
        with server.lock:
            data["settings"] = dict(data["settings"], fontSize=14)
            publish()
        pump()
        paused = bridge.property("position")
        pump(250)
        assert abs(bridge.property("position") - paused) < 1
        QTest.mouseMove(window, QPoint(110, 40))
        pump(150)
        assert panel.property("showControls") is True
        assert panel.property("targetWidth") <= 340
        for panel_height in (24, 42, 84, 120, 42):
            panel.setProperty("height", panel_height)
            pump(80)
            controls = panel.findChild(QObject, "taskbarControls")
            button = next(c for c in controls.findChildren(QObject) if c.property("commandAction") == "next")
            assert button.property("height") <= panel_height
            assert panel.property("targetWidth") <= 340
            start = button.mapToScene(QPointF(0, 0))
            end = button.mapToScene(QPointF(button.property("width"), button.property("height")))
            origin = panel.mapToScene(QPointF(0, 0))
            assert start.y() >= origin.y()
            assert end.y() <= origin.y() + panel_height
            assert start.x() >= origin.x()
            assert end.x() <= origin.x() + panel.property("width")
        next_button = next(c for c in panel.findChildren(QObject) if c.property("commandAction") == "next")
        point = next_button.mapToScene(QPointF(14, 14))
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
        pump(80)
        with server.lock:
            assert any(c["action"] == "next" for c in server.state.commands)
        assert window.property("popupCount") == 0, "button clicks must not trigger body action"
        wheel = QWheelEvent(QPointF(110, 40), QPointF(110, 40), QPoint(0, 0), QPoint(0, 120),
                            Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
        app.sendEvent(window, wheel)
        pump(80)
        with server.lock:
            assert any(c["action"] == "volume" and c["value"] == 0.05 for c in server.state.commands)
        touchpad = QPointingDevice("Test touchpad", 991, QInputDevice.DeviceType.TouchPad,
            QPointingDevice.PointerType.Finger, QInputDevice.Capability.Position, 1, 0)
        cover = panel.findChild(QObject, "taskbarCover")
        points = [cover.mapToScene(QPointF(cover.property("width") / 2, cover.property("height") / 2)),
                  QPointF(110, 40), next_button.mapToScene(QPointF(14, 14))]
        for device, source, pixel, angle in (
            (QPointingDevice.primaryPointingDevice(), Qt.MouseEventNotSynthesized, QPoint(0, 0), QPoint(0, 120)),
            (QPointingDevice.primaryPointingDevice(), Qt.MouseEventSynthesizedBySystem, QPoint(0, 0), QPoint(0, 120)),
            (touchpad, Qt.MouseEventSynthesizedBySystem, QPoint(0, 0), QPoint(0, 120)),
            (touchpad, Qt.MouseEventSynthesizedBySystem, QPoint(0, -20), QPoint(0, 0))):
            for point in points:
                with server.lock: server.state.commands.clear()
                event = QWheelEvent(point, point, pixel, angle, Qt.NoButton, Qt.NoModifier,
                    Qt.ScrollUpdate, False, source, device)
                app.sendEvent(window, event)
                pump(80)
                with server.lock:
                    commands = [c for c in server.state.commands if c["action"] == "volume"]
                    assert len(commands) == 1, "wheel input must reach the widget once from artwork, lyrics and controls"
                    assert commands[0]["value"] == (0.05 if angle.y() > 0 else -0.05)
        # Feedback waits for SP's actual volume, then avoids repeated OSDs on polls.
        server.environment.volume_osds.clear()
        with server.lock:
            data["playback"]["volume"] = .55
            publish()
        pump(650)
        assert server.environment.volume_osds == [55]
        pump(650)
        assert server.environment.volume_osds == [55], "unchanged polls must not redisplay the OSD"
        for volume, direction in ((0, -120), (1, 120)):
            with server.lock:
                data["playback"]["volume"] = volume
                publish()
            pump(1600)
            server.environment.volume_osds.clear()
            event = QWheelEvent(QPointF(110, 40), QPointF(110, 40), QPoint(0, 0), QPoint(0, direction),
                                Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
            app.sendEvent(window, event)
            pump(100)
            assert server.environment.volume_osds == [volume * 100], "volume limits still need feedback"
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(105, 40))
        pump(80)
        assert window.property("popupCount") == 1
        with server.lock:
            data["settings"] = dict(data["settings"], coverPosition="right", lyricMode="single", singlePreferAux=True)
            publish()
        pump()
        assert expression(panel, "bridge.settings.coverPosition") == "right"
        assert expression(second, "bridge.settings.lyricMode") == "single"
        QTest.mouseMove(window, QPoint(900, 660))
        pump(100)
        assert expression(panel, "display.primary") == data["lines"][0]["translatedLyric"]
        with server.lock:
            data["playback"] = dict(data["playback"], state="playing", speed=1.5, timestamp=int(time.time()*1000))
            publish()
        pump()
        before = bridge.property("position")
        pump(200)
        assert bridge.property("position") > before + 200
        with server.lock:
            data["playback"] = dict(data["playback"], state="paused", position=6000, timestamp=int(time.time()*1000))
            data["settings"] = dict(data["settings"], lyricMode="double", coverPosition="left")
            publish()
        pump()
        assert bridge.property("currentIndex") == 1
        popup = window.findChild(QObject, "popup")
        lyric_delegate = expression(popup, "children[0].children[1].itemAtIndex(bridge.currentIndex)")
        if hasattr(lyric_delegate, "toQObject"):
            lyric_delegate = lyric_delegate.toQObject()
        point = lyric_delegate.mapToScene(QPointF(30, 20))
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
        pump(80)
        with server.lock:
            assert any(c["action"] == "seek" and c["value"] == 5000 for c in server.state.commands)
            data["settings"] = dict(data["settings"], clickLyricSeek=False)
            publish()
        pump()
        with server.lock:
            count = len(server.state.commands)
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
        pump(80)
        with server.lock:
            assert len(server.state.commands) == count, "disabled lyric seek must not issue commands"
        with server.lock:
            data["locale"] = "en-US"
            data["settings"] = dict(data["settings"], themeMode="manual", manualDark=False)
            publish()
        pump()
        assert bridge.property("chinese") is False
        assert bridge.property("dark") is False
        with server.lock:
            data["locale"] = "zh-CN"
            data["settings"] = dict(data["settings"], themeMode="splayer")
            publish()
        pump()
        assert bridge.property("dark") is True
        artifacts = ROOT / "artifacts"
        artifacts.mkdir(exist_ok=True)
        assert window.grabWindow().save(str(artifacts / "qml-preview.png"))
        with server.lock:
            server.state.last_seen = -100
            server.state.content_revision += 1
        pump()
        assert panel.property("collapsed") is True
        assert panel.property("targetWidth") < 70
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(35, 40))
        pump(80)
        assert server.environment.launched == 1
        with server.lock:
            server.state.settings["offlineClick"] = "none"
            server.state.content_revision += 1
        pump()
        QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(35, 40))
        pump(80)
        assert server.environment.launched == 1
        with server.lock:
            server.state.settings["offlineDisplay"] = "hidden"
            server.state.content_revision += 1
        pump()
        assert panel.property("targetWidth") == 0
        # Native Plasma Apply copies cfg_ properties to KConfigPropertyMap.
        # Exercise that exact signal path with a real settings control, separate
        # HTTP bridges and a configuration window that can close immediately.
        settings_component = QQmlComponent(engine)
        settings_component.setData(f"""
import QtQuick 2.15
import QtQuick.Window 2.15
import "{ui}" as SPTL
Window {{
    width: 650; height: 850; visible: true
    SPTL.ConfigGeneral {{
        id: configPage; objectName: "configPage"; anchors.fill: parent
        endpoint: "http://127.0.0.1:{port}"
        cfg_settingsRequest: testConfiguration.settingsRequest
        cfg_settingsRequestDefault: ""; cfg_length: 93; cfg_expanding: false
    }}
}}
""".encode(), QUrl("file:///tmp/sptl-settings-smoke.qml"))
        settings_window = settings_component.create()
        assert settings_window, "\n".join(e.toString() for e in settings_component.errors())
        pump()
        config_page = settings_window.findChild(QObject, "configPage")
        font_editor = visual_find(settings_window.contentItem(), "setting_fontSize")
        assert font_editor, "\n".join(errors)
        assert font_editor.property("value") == 14
        point = font_editor.mapToScene(QPointF(80, 15))
        QTest.mouseClick(settings_window, Qt.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
        for _ in range(8):
            QTest.keyClick(settings_window, Qt.Key_Up)
        pump(100)
        assert font_editor.property("value") == 22
        request = config_page.property("cfg_settingsRequest")
        assert json.loads(request)["changes"] == {"fontSize": 22}
        assert settings_window.grabWindow().save(str(artifacts / "qml-settings.png"))
        with server.lock:
            assert server.state.settings["fontSize"] == 14, "edits must wait for Apply"
        expression(config_page, "testConfiguration.settingsRequest = cfg_settingsRequest")
        settings_window.close()
        settings_window.deleteLater()
        settings_window = None
        pump()
        with server.lock:
            assert server.state.settings["fontSize"] == 22
            # A still-running old SP plugin must not undo the Plasma setting.
            server.state.exchange(data)
        pump()
        assert expression(panel, "bridge.settings.fontSize") == 22
        assert panel.property("primarySize") == second.property("primarySize")
        # Closing a second editor without Apply must not submit its draft.
        settings_window = settings_component.create()
        assert settings_window
        pump()
        config_page = settings_window.findChild(QObject, "configPage")
        expression(config_page, 'edit("fontSize", 30)')
        settings_window.close()
        settings_window.deleteLater()
        settings_window = None
        pump()
        with server.lock:
            assert server.state.settings["fontSize"] == 22
        # Recreating an applet must not replay its obsolete Apply request.
        with server.lock:
            server.update_settings({"fontSize": 25})
        sync_component = QQmlComponent(engine)
        sync_component.setData(f"""
import QtQuick 2.15
import "{ui}" as SPTL
SPTL.SettingsSync {{
    property SPTL.Bridge ownBridge: SPTL.Bridge {{ endpoint: "http://127.0.0.1:{port}" }}
    bridge: ownBridge; configuration: testConfiguration
}}
""".encode(), QUrl("file:///tmp/sptl-sync-smoke.qml"))
        restarted_sync = sync_component.create()
        assert restarted_sync, "\n".join(e.toString() for e in sync_component.errors())
        pump(1100)
        with server.lock:
            assert server.state.settings["fontSize"] == 25
        restarted_sync.deleteLater()
        # Check the real Plasma 6 shell entry compiles with installed imports.
        shell = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "dist/plasma6/org.kde.plasma.sptl/contents/ui/main.qml")))
        if shell.status() == QQmlComponent.Error:
            raise AssertionError("\n".join(e.toString() for e in shell.errors()))
        bad = [e for e in errors if "file:" in e]
        assert not bad, "\n".join(bad)
        print("QML live height adaptation, artwork/text/button scaling, unclipped lyrics, native settings and interaction checks passed")
        print("Rendered artifacts/qml-preview.png and artifacts/qml-settings.png")
    finally:
        if settings_window:
            settings_window.close()
            settings_window.deleteLater()
        window.close()
        window.deleteLater()
        app.processEvents()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
