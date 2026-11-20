#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise the real installer under temporary XDG paths and mock only systemd activation."""
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
        original_run = install.run
        def run(*command, **kwargs):
            if Path(command[0]).name == "systemctl":
                commands.append(command)
                return subprocess.CompletedProcess(command, 0)
            return original_run(*command, **kwargs)
        with patch.dict(os.environ, environment), patch.object(install, "run", run):
            with patch.object(sys, "argv", ["install.py",
                                           "--splayer-config", str(base / "SP/settings.json"),
                                           "--splayer-command", "/opt/SPlayer-Next.AppImage"]):
                install.main()
            home = base / "data/sptl"
            assert (home / "helper/sptl/server.py").is_file()
            assert (home / "shared/settings.json").is_file()
            assert (home / "zxaBinbina.sptl.js").is_file()
            unit = base / "config/systemd/user/sptl-bridge.service"
            assert unit.is_file()
            assert any("enable" in command for command in commands)
            assert not any("plasma-plasmashell.service" in command for command in commands)
            subprocess.run([sys.executable, "-c", "from sptl.model import DEFAULTS; assert DEFAULTS['lyricMode'] == 'double'"],
                           cwd=home / "helper", check=True)
            verified = subprocess.run(["systemd-analyze", "verify", str(unit)], capture_output=True, text=True)
            assert verified.returncode == 0, verified.stdout + verified.stderr
            # Update the same version through the real native package tool.
            with patch.object(sys, "argv", ["install.py", "--plasma", "6", "--reload-plasma"]):
                install.main()
            assert any(Path(command[0]).name == "systemctl" and command[1:] ==
                       ("--user", "restart", "plasma-plasmashell.service") for command in commands)
            with patch.object(sys, "argv", ["install.py", "--uninstall"]):
                install.main()
            assert not home.exists()
            assert not unit.exists()
            assert not (base / "data/plasma/plasmoids/org.kde.plasma.sptl").exists()
        print("User-level install/update/uninstall, installed helper import and systemd unit checks passed")
        print("Systemd activation was mocked; the real user session was not modified")


if __name__ == "__main__":
    main()
