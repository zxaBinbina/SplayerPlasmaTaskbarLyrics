#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise animation interruption, layout bounds and asynchronous artwork."""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
from sptl.model import DEFAULTS, normalize_lines

from PySide6.QtCore import QBuffer, QIODevice, QObject, QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest


def main():
    app = QGuiApplication(sys.argv)
    png = QBuffer()
    png.open(QIODevice.WriteOnly)
    bitmap = QImage(16, 16, QImage.Format_RGB32)
    bitmap.fill(QColor("#fe7971"))
    assert bitmap.save(png, "PNG")
    image_bytes = bytes(png.data())
    requested, release = threading.Event(), threading.Event()

    class Images(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/slow.png":
                requested.set()
                release.wait(3)
            if self.path == "/missing.png":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(image_bytes)))
            self.end_headers()
            self.wfile.write(image_bytes)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Images)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    engine = QQmlEngine()
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
    lines = normalize_lines([
        {"startTime": i * 2000, "endTime": (i + 1) * 2000,
         "words": [{"word": f"第 {i + 1} 句歌词", "startTime": i * 2000, "endTime": (i + 1) * 2000}]}
        for i in range(30)
    ])
    component = QQmlComponent(engine)
    ui = (ROOT / "dist/plasma6/org.kde.plasma.sptl/contents/ui").as_uri()
    image_url = f"http://127.0.0.1:{server.server_address[1]}"
    component.setData(f"""
import QtQuick 2.15
import QtQuick.Window 2.15
import "{ui}" as SPTL
Window {{
    width: 800; height: 640; visible: true; color: "#131316"
    QtObject {{
        id: testBridge; objectName: "bridge"
        property var settings: {json.dumps(dict(DEFAULTS, auxiliary="off", maxWidth=420))}
        property var track: ({{ title: "歌曲名称", artists: "演示歌手" }})
        property var playback: ({{ duration: 60000, offset: 0 }})
        property var lines: {json.dumps(lines, ensure_ascii=False)}
        property int currentIndex: 0
        property real position: 500
        property real lyricPosition: position
        property bool running: true
        property bool connected: true
        property bool playing: false
        property bool hidden: false
        property color foreground: "#f5f5f5"
        property color secondary: "#b9b9bd"
        property color accent: "#fe7971"
        property color background: "#202124"
        property string lastError: ""
        property string coverSource: "{image_url}/good.png"
        readonly property int motionDuration: settings.animationsEnabled ? 200 : 0
        readonly property int quickDuration: settings.animationsEnabled ? 100 : 0
        function tr(zh, en) {{ return zh; }}
        function statusText() {{ return "SPlayer Next"; }}
        function command(action, value) {{}}
    }}
    SPTL.Taskbar {{
        objectName: "panel"; x: 20; y: 20; width: implicitWidth; height: 42
        bridge: testBridge
    }}
    SPTL.FullLyrics {{
        objectName: "popup"; x: 20; y: 80; width: 480; height: 540
        bridge: testBridge
    }}
    SPTL.Marquee {{
        objectName: "timed"; x: 530; y: 80; width: 90
        text: "逐字歌词滚动验证"; transitionDuration: testBridge.motionDuration
        words: [{{word: "逐字", startTime: 0, endTime: 1000}},
                {{word: "歌词滚动验证", startTime: 1000, endTime: 3000}}]
        position: testBridge.position
    }}
    SPTL.Cover {{
        objectName: "artwork"; x: 530; y: 130; width: 64; height: 64
        source: testBridge.coverSource; transitionDuration: testBridge.motionDuration
    }}
}}
""".encode(), QUrl("file:///tmp/sptl-animations.qml"))
    window = component.create()
    assert window, "\n".join(e.toString() for e in component.errors())

    def expression(obj, source):
        value = QQmlExpression(engine.rootContext(), obj, source)
        result = value.evaluate()
        assert not value.hasError(), value.error().toString()
        return result[0] if isinstance(result, tuple) else result

    def pump(duration=30):
        deadline = time.monotonic() + duration / 1000
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)

    def until(predicate, timeout=1500):
        deadline = time.monotonic() + timeout / 1000
        while not predicate() and time.monotonic() < deadline:
            pump(10)
        assert predicate(), "animation or image did not settle"

    bridge = window.findChild(QObject, "bridge")
    panel = window.findChild(QObject, "panel")
    popup = window.findChild(QObject, "popup")
    primary = panel.findChild(QObject, "primaryLyric")
    artwork = window.findChild(QObject, "artwork")
    timed = window.findChild(QObject, "timed")
    lyrics = popup.findChild(QObject, "fullLyricsList")
    try:
        pump(250)
        until(lambda: artwork.property("activeSlot") >= 0)
        expression(bridge, "currentIndex = 1")
        pump()
        assert primary.property("transitioning")
        # Several updates during one animation must show the latest text.
        expression(bridge, "currentIndex = 2; currentIndex = 3")
        assert primary.property("text") == lines[3]["text"]
        until(lambda: not primary.property("transitioning"))
        assert primary.property("text") == lines[3]["text"]

        frozen = timed.property("highlightWidth"), timed.property("offset")
        pump(150)
        assert frozen == (timed.property("highlightWidth"), timed.property("offset"))
        expression(bridge, "position = 2200")
        assert timed.property("highlightWidth") > frozen[0]

        start_width = panel.property("layoutWidth")
        expression(bridge, 'track = ({title: "很长的歌曲名称，需要更多空间来显示歌曲信息", artists: "演示歌手"})')
        QTest.mouseMove(window, QPoint(80, 40))
        pump()
        assert panel.property("showControls")
        assert 0 < panel.property("controlsProgress") < 1
        assert start_width < panel.property("layoutWidth") < panel.property("targetWidth")
        QTest.mouseMove(window, QPoint(760, 620))
        pump()
        QTest.mouseMove(window, QPoint(80, 40))
        pump()
        until(lambda: panel.property("controlsProgress") == 1)
        assert panel.property("layoutWidth") <= 420

        expression(bridge, 'settings = Object.assign({}, settings, {maxWidth: 180})')
        assert panel.property("layoutWidth") <= 180, "maximum width must apply during a resize"
        expression(bridge, 'settings = Object.assign({}, settings, {coverPosition: "right"})')
        pump(250)
        controls = panel.findChild(QObject, "taskbarControls")
        toggle = next(c for c in controls.findChildren(QObject) if c.property("commandAction") == "toggle")
        point = toggle.mapToScene(QPointF(toggle.property("width") / 2, toggle.property("height") / 2))
        click = QPoint(round(point.x()), round(point.y()))
        QTest.mouseMove(window, click)
        pump(120)
        assert expression(toggle, "contentItem.scale") > 1, (
            click, toggle.property("hovered"), toggle.property("hoverEnabled"),
            panel.property("hovered"), panel.property("showControls"), panel.property("controlsProgress"),
            expression(toggle, "contentItem.scale"))
        QTest.mousePress(window, Qt.LeftButton, pos=click)
        pump(120)
        assert expression(toggle, "contentItem.scale") < 1
        QTest.mouseRelease(window, Qt.LeftButton, pos=click)

        previous = lyrics.property("contentY")
        expression(bridge, "currentIndex = 20")
        pump(60)
        middle = lyrics.property("contentY")
        assert middle > previous
        pump(350)
        assert lyrics.property("contentY") > middle
        # User interaction takes ownership of scrolling and cancels following.
        QTest.mousePress(window, Qt.LeftButton, pos=QPoint(250, 320))
        QTest.mouseMove(window, QPoint(250, 350), delay=30)
        QTest.mouseMove(window, QPoint(250, 380), delay=30)
        QTest.mouseRelease(window, Qt.LeftButton, pos=QPoint(250, 380))
        until(lambda: not lyrics.property("moving"))
        assert not popup.property("following")
        stopped = lyrics.property("contentY")
        expression(bridge, "currentIndex = 25")
        pump(350)
        assert not popup.property("following")
        assert lyrics.property("contentY") == stopped
        expression(popup, "following = true; follow()")
        pump(30)

        old_slot = artwork.property("activeSlot")
        expression(bridge, f'coverSource = "{image_url}/slow.png"')
        until(requested.is_set)
        assert artwork.property("loading")
        assert artwork.property("activeSlot") == old_slot, "keep artwork while the next cover loads"
        release.set()
        until(lambda: not artwork.property("loading"))
        assert artwork.property("activeSlot") != old_slot
        # Disabling animations must finish any ongoing transition immediately.
        expression(bridge, 'settings = Object.assign({}, settings, {animationsEnabled: false}); currentIndex = 27')
        pump(20)
        assert not primary.property("transitioning")
        assert panel.property("layoutWidth") == panel.property("targetWidth")
        settled = lyrics.property("contentY")
        expression(popup, "follow(true)")
        assert lyrics.property("contentY") == settled
        pump(350)
        assert lyrics.property("contentY") == settled
        QTest.mouseMove(window, QPoint(760, 620))
        pump(20)
        assert panel.property("controlsProgress") == 0
        expression(bridge, "hidden = true")
        assert panel.property("layoutWidth") == 0
        assert not panel.property("visible")

        expression(bridge, f'coverSource = "{image_url}/missing.png"')
        until(lambda: artwork.property("activeSlot") == -1)
        expression(bridge, f'coverSource = "{image_url}/good.png"')
        until(lambda: artwork.property("activeSlot") >= 0)
        # Image.Error is expected here; all other project warnings are failures.
        unexpected = [e for e in errors if "file:" in e and "/missing.png" not in e]
        assert not unexpected, "\n".join(unexpected)
        print("QML lyric/hover/width/button/follow animations, interruption, pause and artwork checks passed")
    finally:
        release.set()
        window.close()
        window.deleteLater()
        app.processEvents()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
