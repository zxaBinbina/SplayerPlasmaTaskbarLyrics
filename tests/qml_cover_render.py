#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Verify the actual alpha mask on Qt's accelerated renderer."""
import os
import time
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if "--desktop" in sys.argv:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    display = next(path.name for path in runtime.glob("wayland-*") if path.is_socket())
    os.environ.update(QT_QPA_PLATFORM="wayland", WAYLAND_DISPLAY=display, XDG_RUNTIME_DIR=str(runtime),
                      DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(runtime / "bus"))
os.environ.pop("QT_QUICK_BACKEND", None)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QImage, QColor
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuick import QSGRendererInterface
root = Path(__file__).resolve().parents[1]
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
image_path = artifacts / "solid-cover.png"
img = QImage(100,100,QImage.Format_RGB32)
img.fill(QColor("#fe7971"))
assert img.save(str(image_path))
QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGL)
app = QGuiApplication([])
engine = QQmlEngine()
warnings = []
engine.warnings.connect(lambda entries: warnings.extend(x.toString() for x in entries))
component = QQmlComponent(engine)
ui = (root / "dist/plasma6/org.kde.plasma.sptl/contents/ui").as_uri()
component.setData(f'''import QtQuick 2.15
import QtQuick.Window 2.15
import "{ui}" as SPTL
Window {{ width:320; height:160; visible:true; color:"#121212"
    SPTL.Cover {{ x:20; y:20; width:120; height:120; circular:true; source:"{image_path.as_uri()}" }}
    SPTL.Cover {{ x:180; y:20; width:120; height:120; source:"{image_path.as_uri()}" }}
}}'''.encode(), QUrl("file:///tmp/sptl-cover-render.qml"))
window = component.create()
assert window, "\n".join(x.toString() for x in component.errors())
try:
    end = time.monotonic() + 1
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.01)
    shot = window.grabWindow()
    assert shot.save(str(artifacts / "qml-cover-shapes.png"))
    scale = shot.devicePixelRatio()
    def color(x, y): return shot.pixelColor(round(x * scale), round(y * scale)).name()
    assert color(22,22) == "#121212", "circular corners must be transparent"
    assert color(80,80) == "#fe7971", "circular center must retain artwork"
    assert color(182,22) == "#fe7971", "square corners retain artwork"
    assert not warnings, "\n".join(warnings)
    print("Actual Qt rendering of circular and square artwork passed")
finally:
    window.close()
    window.deleteLater()
    app.processEvents()
