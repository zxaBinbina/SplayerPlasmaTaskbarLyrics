#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate native packaging in an isolated XDG directory."""
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    for version in (5, 6):
        archive = ROOT / f"dist/sptl-plasma{version}-1.0.1.plasmoid"
        with zipfile.ZipFile(archive) as package:
            assert package.testzip() is None
            assert {"metadata.json", "contents/ui/main.qml", "contents/ui/Defaults.js",
                    "contents/config/main.xml", "contents/config/config.qml",
                    "contents/ui/ConfigGeneral.qml", "contents/ui/SettingsSync.qml",
                    "contents/ui/FullLyrics.qml", "contents/images/sptl.png",
                    "LICENSE", "THIRD_PARTY.md"}.issubset(package.namelist())
            if version == 5:
                assert "metadata.desktop" in package.namelist()
    tool = shutil.which("kpackagetool6")
    if not tool:
        print("Archive checks passed; native Plasma 6 package check skipped (tool unavailable)")
        return
    with tempfile.TemporaryDirectory(prefix="sptl-package-") as directory:
        sandbox = Path(directory)
        env = dict(os.environ, XDG_DATA_HOME=str(sandbox / "data"),
                   XDG_CONFIG_HOME=str(sandbox / "config"), XDG_CACHE_HOME=str(sandbox / "cache"),
                   QT_QPA_PLATFORM="offscreen")
        root = sandbox / "data/plasma/plasmoids"
        root.mkdir(parents=True)
        base = [tool, "--type", "Plasma/Applet", "--packageroot", str(root)]
        source = ROOT / "dist/plasma6/org.kde.plasma.sptl"
        def run(*args, check=True):
            result = subprocess.run(base + list(args), env=env, text=True,
                                    capture_output=True, timeout=20)
            if check and result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            return result
        run("--install", str(source))
        installed = root / "org.kde.plasma.sptl"
        assert (installed / "contents/ui/main.qml").is_file()
        run("--show", "org.kde.plasma.sptl")
        upgrade = run("--upgrade", str(source), check=False)
        print("Same-version native upgrade:", upgrade.returncode, (upgrade.stdout + upgrade.stderr).strip())
        run("--remove", "org.kde.plasma.sptl")
        assert not installed.exists()
        print("Both archives and isolated Plasma 6 install/show/remove checks passed")


if __name__ == "__main__":
    main()
