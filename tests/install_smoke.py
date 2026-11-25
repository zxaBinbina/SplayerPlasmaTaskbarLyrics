#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Verify helper-only install/update/uninstall without touching store-managed files."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import install


def main():
    with tempfile.TemporaryDirectory(prefix="sptl install ") as directory:
        base = Path(directory)
        environment = {"XDG_DATA_HOME": str(base / "data"),
                       "XDG_CONFIG_HOME": str(base / "config"),
                       "XDG_STATE_HOME": str(base / "state"),
                       "XDG_CACHE_HOME": str(base / "cache"),
                       "QT_QPA_PLATFORM": "offscreen"}
        commands = []
        def run(*command, **kwargs):
            assert Path(command[0]).name == "systemctl", command
            commands.append(command)
            return subprocess.CompletedProcess(command, 0)
        with patch.dict(os.environ, environment), patch.object(install, "run", run):
            with patch.object(sys, "argv", ["install.py",
                                           "--splayer-config", str(base / "SP/settings.json"),
                                           "--splayer-command", "/opt/SPlayer-Next.AppImage"]):
                install.main()
            home = base / "data/sptl"
            assert (home / "helper/sptl/server.py").is_file()
            assert (home / "shared/settings.json").is_file()
            assert not (home / "zxaBinbina.sptl.js").exists()
            widget = base / "data/plasma/plasmoids/org.kde.plasma.sptl"
            assert not widget.exists()
            unit = base / "config/systemd/user/sptl-bridge.service"
            assert unit.is_file()
            assert any("enable" in command for command in commands)
            assert not any("plasma-plasmashell.service" in command for command in commands)
            subprocess.run([sys.executable, "-c", "from sptl.model import DEFAULTS; assert DEFAULTS['lyricMode'] == 'double'"],
                           cwd=home / "helper", check=True)
            verified = subprocess.run(["systemd-analyze", "verify", str(unit)], capture_output=True, text=True)
            assert verified.returncode == 0, verified.stdout + verified.stderr
            # Store files and legacy plugin copies must survive helper updates and removal.
            widget.mkdir(parents=True)
            (widget / "store-file").write_text("store managed")
            plugin = home / "zxaBinbina.sptl.js"
            plugin.write_text("legacy plugin")
            settings = base / "state/sptl/settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text('{"fontSize": 24}')
            original_unit = unit.read_text()
            command_count = len(commands)
            with patch.object(sys, "argv", ["install.py"]), \
                 patch.object(install, "choose_installed_action", return_value="cancel") as choose:
                install.main()
                choose.assert_called_once()
            assert len(commands) == command_count
            assert unit.read_text() == original_unit
            with patch.object(sys, "argv", ["install.py", "--plasma", "6", "--reload-plasma"]), \
                 patch.object(install, "choose_installed_action", return_value="upgrade") as choose:
                install.main()
                choose.assert_called_once()
            assert unit.read_text() == original_unit
            assert settings.read_text() == '{"fontSize": 24}'
            assert plugin.read_text() == "legacy plugin"
            assert (widget / "store-file").read_text() == "store managed"
            assert not any("plasma-plasmashell.service" in command for command in commands)
            with patch.object(sys, "argv", ["install.py"]), \
                 patch.object(install, "choose_installed_action", return_value="uninstall") as choose:
                install.main()
                choose.assert_called_once()
            assert not (home / "helper").exists()
            assert not (home / "shared").exists()
            assert not unit.exists()
            assert plugin.read_text() == "legacy plugin"
            assert (widget / "store-file").read_text() == "store managed"
            assert settings.read_text() == '{"fontSize": 24}'
            # An explicit purge also works after a normal uninstall preserved settings.
            with patch.object(sys, "argv", ["install.py", "--uninstall", "--purge"]):
                install.main()
            assert not settings.parent.exists()
            assert plugin.read_text() == "legacy plugin"
            assert (widget / "store-file").read_text() == "store managed"
        print("Helper-only install/update/uninstall, preserved store files/settings, helper import and systemd unit checks passed")
        print("Systemd activation was mocked; the real user session was not modified")


if __name__ == "__main__":
    main()
