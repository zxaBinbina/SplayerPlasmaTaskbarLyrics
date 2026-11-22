#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Install/update/remove only SPTL's user-level files; no administrator access."""
import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from build import build, ROOT

APPLET = "org.kde.plasma.sptl"


def session_environment():
    """Recover the current user's bus for shells launched outside a desktop terminal."""
    environment = dict(os.environ)
    if not environment.get("XDG_RUNTIME_DIR"):
        runtime = Path(f"/run/user/{os.getuid()}")
        if runtime.is_dir() and runtime.stat().st_uid == os.getuid():
            environment["XDG_RUNTIME_DIR"] = str(runtime)
    runtime_dir = environment.get("XDG_RUNTIME_DIR")
    if not environment.get("DBUS_SESSION_BUS_ADDRESS") and runtime_dir:
        bus = Path(runtime_dir) / "bus"
        if bus.is_socket() and bus.stat().st_uid == os.getuid():
            environment["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + str(bus)
    return environment


def run(*command, check=True, capture_output=False):
    environment = session_environment()
    if Path(command[0]).name.startswith("kpackagetool"):
        environment["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(command, check=check, capture_output=capture_output,
                          text=True, env=environment)


def detect_plasma():
    environment = session_environment()
    version = environment.get("KDE_SESSION_VERSION")
    if version in ("5", "6"):
        return version
    shell = shutil.which("plasmashell")
    if not shell:
        raise ValueError("plasmashell was not found")
    # --version is a GUI executable too. It must not require a display connection.
    environment["QT_QPA_PLATFORM"] = "offscreen"
    try:
        result = subprocess.run([shell, "--version"], env=environment, capture_output=True,
                                text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("plasmashell --version could not run") from error
    if result.returncode:
        raise ValueError(f"plasmashell --version exited with code {result.returncode}")
    match = re.search(r"\bplasmashell\s+(5|6)\.", result.stdout + "\n" + result.stderr)
    if not match:
        raise ValueError("unrecognized plasmashell version output")
    return match.group(1)


def unit_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plasma", choices=("5", "6"), help="Select Plasma version explicitly")
    parser.add_argument("--reload-plasma", action="store_true",
                        help="Reload the running Plasma shell after updating cached widget code")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--purge", action="store_true", help="Also remove saved shared settings")
    parser.add_argument("--splayer-config", help="SP app-data/config/settings.json")
    parser.add_argument("--splayer-command", help="Launch command, e.g. '/path/SPlayer-Next.AppImage'")
    args = parser.parse_args()
    if args.reload_plasma and args.uninstall:
        parser.error("--reload-plasma cannot be combined with --uninstall")
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    install = data / "sptl"
    unit = config / "systemd/user/sptl-bridge.service"
    if args.uninstall:
        run("systemctl", "--user", "disable", "--now", "sptl-bridge.service", check=False)
        unit.unlink(missing_ok=True)
        for path in (install, data / "plasma/plasmoids" / APPLET):
            if path.is_dir():
                shutil.rmtree(path)
        if args.purge:
            saved = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sptl"
            if saved.is_dir():
                shutil.rmtree(saved)
        run("systemctl", "--user", "daemon-reload", check=False)
        print("Removed SPTL. Remove the SP plugin in SP plugin management.")
        return
    if args.purge:
        parser.error("--purge requires --uninstall")
    if args.plasma:
        version = args.plasma
    else:
        try:
            version = detect_plasma()
        except ValueError as error:
            parser.error(f"Cannot detect Plasma: {error}; specify --plasma 5 or --plasma 6")
    package_tool = shutil.which(f"kpackagetool{version}")
    systemctl = shutil.which("systemctl")
    if not package_tool or not systemctl:
        parser.error(f"kpackagetool{version} and a systemd user session are required")
    manager = run(systemctl, "--user", "show-environment", check=False, capture_output=True)
    if manager.returncode:
        parser.error("Cannot connect to the systemd user session; run this installer from your KDE desktop terminal")
    if args.reload_plasma:
        shell = run(systemctl, "--user", "is-active", "plasma-plasmashell.service",
                    check=False, capture_output=True)
        if shell.returncode:
            parser.error("--reload-plasma requires an active plasma-plasmashell.service; log out and back in after updating")
    dist = build()
    install.mkdir(parents=True, exist_ok=True)
    for directory in ("helper", "shared"):
        target = install / directory
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ROOT / directory, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("LICENSE", "THIRD_PARTY.md"):
        shutil.copy2(ROOT / name, install / name)
    shutil.copy2(dist / "zxaBinbina.sptl.js", install / "zxaBinbina.sptl.js")
    applet_exists = (data / "plasma/plasmoids" / APPLET).exists()
    package = dist / f"plasma{version}" / APPLET
    run(package_tool, "--type", "Plasma/Applet", "--upgrade" if applet_exists else "--install", str(package))
    command = [sys.executable, "-m", "sptl.server"]
    if args.splayer_config:
        command += ["--splayer-config", str(Path(args.splayer_config).expanduser().resolve())]
    if args.splayer_command:
        command += ["--splayer-command", *shlex.split(args.splayer_command)]
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(
        "[Unit]\nDescription=SPlayer Plasma Taskbar Lyrics bridge\nAfter=graphical-session.target\n"
        "\n[Service]\nType=simple\nWorkingDirectory=" + str(install / "helper").replace("%", "%%") +
        "\nExecStart=" + " ".join(unit_quote(c) for c in command) +
        "\nRestart=on-failure\nRestartSec=2\nUMask=0077\n"
        "\n[Install]\nWantedBy=default.target\n"
    )
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "enable", "--now", "sptl-bridge.service")
    run("systemctl", "--user", "restart", "sptl-bridge.service")
    if args.reload_plasma:
        print("Reloading Plasma to discard cached widget code; application windows stay open.", flush=True)
        run(systemctl, "--user", "restart", "plasma-plasmashell.service")
    print(f"Import {install / 'zxaBinbina.sptl.js'} in SP, enable network/control/api permissions,")
    print("then add SPTL to a horizontal Plasma panel. Right-click SPTL to configure shared settings.")
    if applet_exists and not args.reload_plasma:
        print("Plasma can cache old QML even after re-adding a widget. Use --reload-plasma or log out/in to load updated code.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Installation failed: {shlex.join(error.cmd)} (exit {error.returncode})", file=sys.stderr)
        sys.exit(1)
    except OSError as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        sys.exit(1)
