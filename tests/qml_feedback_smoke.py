#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise optimistic QML controls against delayed and failing real HTTP requests."""
import io
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
sys.path.insert(0, str(ROOT / "tests"))
from sptl.server import BridgeServer, Handler
from test_core import snapshot
from PySide6.QtCore import QObject, QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest


class Environment:
    running = True
    locale = "zh-CN"
    theme = {"available": True, "mode": "dark", "accent": "#fe7971"}
    favorite = {"available": True, "liked": False}
    def refresh(self): pass
    def local_cover(self, cover): return None
    def set_favorite(self, liked): self.favorite = {"available": True, "liked": liked}
    def activate(self): pass
    def show_volume(self, percent): pass


class DelayedHandler(Handler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        payload = json.loads(raw)
        if self.path == "/command":
            key = payload["action"], payload["inputSequence"]
            self.server.received.append(payload)
            gate = self.server.gates.get(key)
            if gate:
                gate.wait(2)
                if key in self.server.failures:
                    return self.respond(503, {"error": "simulated send failure"})
        self.rfile = io.BytesIO(raw)
        super().do_POST()


def main():
    app = QGuiApplication([])
    environment = Environment()
    server = BridgeServer(("127.0.0.1", 0), environment=environment)
    server.RequestHandlerClass = DelayedHandler
    server.received, server.gates, server.failures = [], {}, set()
    data = snapshot(modeAvailable=True)
    data["track"] = {"id": "one", "source": "local", "path": "/music/one", "title": "One"}
    second = {"id": "two", "source": "local", "path": "/music/two", "title": "Two"}
    data["playback"].update(state="paused", position=4000, duration=60000, volume=.4, repeat="one", shuffle="off")
    data["queue"] = {"available": True, "tracks": [data["track"], second], "total": 2, "offset": 0, "currentIndex": 0}
    data["lines"] = [{"startTime": 0, "endTime": 10000, "lyric": "First"}, {"startTime": 10000, "endTime": 30000, "lyric": "Second"}]
    server.state.exchange(data)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda entries: warnings.extend(entry.toString() for entry in entries))
    ui = (ROOT / "dist/plasma6/org.kde.plasma.sptl/contents/ui").as_uri()
    component = QQmlComponent(engine)
    component.setData(f'''
import QtQuick 2.15
import QtQuick.Window 2.15
import "{ui}" as SPTL
Window {{
    width: 720; height: 680; visible: true
    SPTL.Bridge {{ id: live; objectName: "bridge"; endpoint: "http://127.0.0.1:{server.server_address[1]}" }}
    SPTL.Controls {{ objectName: "controls"; bridge: live; showFavorite: true; x: 20; y: 20 }}
    SPTL.FullLyrics {{ objectName: "popup"; bridge: live; x: 20; y: 80; width: 480; height: 560 }}
}}
'''.encode(), QUrl("file:///tmp/sptl-feedback.qml"))
    window = component.create()
    assert window, [error.toString() for error in component.errors()]
    bridge = window.findChild(QObject, "bridge")
    controls = window.findChild(QObject, "controls")
    toggle = next(item for item in controls.findChildren(QObject) if item.property("commandAction") == "toggle")
    favorite = controls.findChild(QObject, "hoverFavoriteButton")

    def pump(ms=40):
        until = time.monotonic() + ms / 1000
        while time.monotonic() < until:
            if server.state.clock() - server.state.last_seen > .8:
                with server.lock: server.state.exchange(data)
            app.processEvents()
            time.sleep(.003)
    def wait(predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline: pump()
        assert predicate(), "feedback/request did not settle"
    def expression(code):
        query = QQmlExpression(engine.rootContext(), bridge, code)
        value = query.evaluate()
        assert not query.hasError(), query.error().toString()
        return value[0] if isinstance(value, tuple) else value
    def command(action, value=None):
        return expression("command(" + json.dumps(action) + "," + json.dumps(value) + ")")
    def click(item):
        point = item.mapToScene(QPointF(item.property("width") / 2, item.property("height") / 2))
        QTest.mouseClick(window, Qt.LeftButton, pos=point.toPoint())
    def blocked(action, fail=True):
        request_id = bridge.property("commandSerial") + 1
        key = action, request_id
        gate = threading.Event()
        server.gates[key] = gate
        if fail: server.failures.add(key)
        return request_id, gate
    def received(request_id):
        return any(payload["inputSequence"] == request_id for payload in server.received)
    def queued(action):
        return next((entry for entry in reversed(server.state.commands) if entry["action"] == action), None)
    def publish(completed=None, success=True):
        if completed:
            data["ack"] = [completed["id"]]
            data["results"] = [{"id": completed["id"], "ok": success, "error": "" if success else "control_failed"}]
        with server.lock: server.state.exchange(data)
        expression("revision = -1; poll()")
        pump(650)

    try:
        wait(lambda: bridge.property("connected") and bridge.property("favoriteAvailable"))
        first, gate = blocked("toggle")
        click(toggle)
        assert bridge.property("playing") and toggle.property("iconName") == "media-playback-pause"
        assert server.state.playback["state"] == "paused", "the UI must change before the delayed request is applied"
        wait(lambda: received(first))
        mode_id = command("mode", "one")
        assert bridge.property("playbackMode") == "one"
        wait(lambda: received(mode_id) and queued("mode") is not None)
        publish(queued("mode"))
        gate.set()
        wait(lambda: not bridge.property("playing"))
        assert bridge.property("playbackMode") == "one", "a failed playback request must not undo another control"

        older, gate = blocked("toggle")
        click(toggle)
        assert bridge.property("playing")
        click(toggle)
        latest = bridge.property("commandSerial")
        assert not bridge.property("playing")
        wait(lambda: received(latest) and queued("toggle") is not None)
        publish(queued("toggle"))
        gate.set(); pump(150)
        assert not bridge.property("playing"), "an older failure must not undo a newer toggle"
        assert next(payload for payload in server.received if payload["inputSequence"] == latest)["value"] == "paused"

        favorite_id, gate = blocked("favorite")
        click(favorite)
        assert favorite.property("checked")
        wait(lambda: received(favorite_id))
        gate.set()
        wait(lambda: not favorite.property("checked"))
        command("mode", "shuffle")
        assert bridge.property("playbackMode") == "shuffle"
        wait(lambda: queued("mode") is not None)
        publish(queued("mode"), success=False)
        assert bridge.property("playbackMode") == "one", "correlated execution failure must also restore feedback"

        seek_id, gate = blocked("seek")
        command("seek", 20000)
        assert abs(bridge.property("position") - 20000) < 1
        wait(lambda: received(seek_id)); gate.set()
        wait(lambda: abs(bridge.property("position") - 4000) < 1)
        selection_id, gate = blocked("queuePlay")
        command("queuePlay", {"index": 1, **{key: second[key] for key in ("id", "source", "path")}})
        assert bridge.property("queueSelectionIndex") == 1
        wait(lambda: received(selection_id)); gate.set()
        wait(lambda: bridge.property("queueSelectionIndex") == 0)

        with server.lock: server.update_settings({"instantFeedback": False})
        publish()
        assert not bridge.property("instantFeedback")
        toggle_id, toggle_gate = blocked("toggle", fail=False)
        click(toggle)
        assert not bridge.property("playing"), "disabled feedback must retain the real playback state"
        favorite_id, favorite_gate = blocked("favorite", fail=False)
        click(favorite)
        assert not favorite.property("checked"), "disabled feedback must retain the real favorite state"
        mode_id, mode_gate = blocked("mode", fail=False)
        command("mode", "shuffle")
        assert bridge.property("playbackMode") == "one"
        wait(lambda: all(received(request_id) for request_id in (toggle_id, favorite_id, mode_id)))
        assert not expression("actionPending('toggle')")
        toggle_gate.set(); favorite_gate.set(); mode_gate.set()
        wait(lambda: queued("toggle") is not None and queued("mode") is not None)
        data["playback"].update(state="playing", repeat="list", shuffle="on")
        data["ack"] = [entry["id"] for entry in server.state.commands]
        data["results"] = [{"id": value, "ok": True} for value in data["ack"]]
        publish()
        assert bridge.property("playing") and favorite.property("checked") and bridge.property("playbackMode") == "shuffle"

        with server.lock: server.update_settings({"instantFeedback": True})
        publish()
        volume_id, gate = blocked("setVolume")
        command("setVolume", .6)
        assert abs(bridge.property("volume") - .6) < .001
        wait(lambda: received(volume_id)); gate.set()
        wait(lambda: abs(bridge.property("volume") - .4) < .001)
        assert not warnings, "\n".join(warnings)
        print("Instant button/seek/selection feedback, parallel sends, request/result rollback, latest-intent protection and feedback-off checks passed")
    finally:
        for gate in server.gates.values(): gate.set()
        window.close(); window.deleteLater(); app.processEvents()
        server.shutdown(); server.server_close(); worker.join()


if __name__ == "__main__":
    main()
