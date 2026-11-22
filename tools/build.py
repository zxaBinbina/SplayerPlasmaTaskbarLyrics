#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Produce a standalone official-API plugin and separate Plasma 5/6 packages."""
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.1"
PLUGIN_ID = "zxaBinbina.sptl"


def build():
    schema = json.loads((ROOT / "shared/settings.json").read_text())
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    plugin = dist / (PLUGIN_ID + ".js")
    header = f"""/**
 * @name SPTL 任务栏歌词
 * @id {PLUGIN_ID}
 * @version {VERSION}
 * @author zxaBinbina
 * @type control
 * @grant network control api
 * @apiLevel 5
 * @updateUrl https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics/releases/latest/download/zxaBinbina.sptl.js
 * @description KDE Plasma 5/6 任务栏同步歌词、封面和播放控制。需安装 SPTL 辅助程序与小部件。
 * @homepage https://github.com/zxaBinbina/SplayerPlasmaTaskbarLyrics
 */
// SPDX-License-Identifier: AGPL-3.0-only
"""
    plugin.write_text(header + (ROOT / "plugin/runtime.js").read_text())
    defaults = ".pragma library\n// Generated from shared/settings.json by tools/build.py\nvar settings = " + json.dumps({s["key"]: s["default"] for s in schema}) + ";\nvar schema = " + json.dumps(schema, ensure_ascii=False) + ";\n"
    for version in (5, 6):
        package = dist / f"plasma{version}" / "org.kde.plasma.sptl"
        if package.exists():
            shutil.rmtree(package)
        shutil.copytree(ROOT / "plasmoid/contents", package / "contents")
        (package / "contents/ui/Defaults.js").write_text(defaults)
        shutil.copy2(ROOT / "LICENSE", package / "LICENSE")
        shutil.copy2(ROOT / "THIRD_PARTY.md", package / "THIRD_PARTY.md")
        metadata = json.loads((ROOT / "plasmoid/metadata.json").read_text())
        metadata["X-Plasma-API-Minimum-Version"] = "5.27" if version == 5 else "6.0"
        (package / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        if version == 5:
            metadata.update({"X-Plasma-API": "declarativeappletscript",
                             "X-Plasma-MainScript": "ui/main.qml", "X-KDE-ServiceTypes": ["Plasma/Applet"]})
            (package / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
            shutil.copy2(ROOT / "plasmoid/plasma5/main.qml", package / "contents/ui/main.qml")
            shutil.copy2(ROOT / "plasmoid/plasma5/CoverMask.qml", package / "contents/ui/CoverMask.qml")
            shutil.copy2(ROOT / "plasmoid/plasma5/metadata.desktop", package / "metadata.desktop")
        archive = dist / f"sptl-plasma{version}-{VERSION}.plasmoid"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    stream.write(path, path.relative_to(package))
    print(f"Built {plugin.relative_to(ROOT)}, Plasma 5 and Plasma 6 packages")
    return dist


if __name__ == "__main__":
    build()
