#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Install/update/remove the SPTL helper; widgets and plugins use their stores."""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    return subprocess.run(command, check=check, capture_output=capture_output,
                          text=True, env=environment)


def previous_options(unit):
    if not unit.is_file():
        return {}
    lines = [line[len("ExecStart="):] for line in unit.read_text().splitlines()
             if line.startswith("ExecStart=")]
    if len(lines) != 1:
        raise ValueError(f"Cannot read the existing helper service: {unit}")
    arguments = shlex.split(lines[0].replace("%%", "%"))
    options = {}
    if "--splayer-config" in arguments:
        index = arguments.index("--splayer-config") + 1
        if index >= len(arguments):
            raise ValueError("The existing --splayer-config option has no value")
        options["splayer_config"] = arguments[index]
    if "--splayer-command" in arguments:
        index = arguments.index("--splayer-command") + 1
        end = next((position for position in range(index, len(arguments))
                    if arguments[position] == "--splayer-config"), len(arguments))
        if index == end:
            raise ValueError("The existing --splayer-command option has no value")
        options["splayer_command"] = shlex.join(arguments[index:end])
    return options


def unit_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'

def choose_installed_action():
    try:
        reader = open('/dev/tty', 'r', encoding='utf-8')
        writer = open('/dev/tty', 'w', encoding='utf-8')
    except OSError as error:
        raise ValueError('已安装辅助程序。请在终端再次运行，或指定 --upgrade、--uninstall。') from error
    with reader, writer:
        writer.write('检测到已安装 SPTL 辅助程序。\n1. 升级\n2. 卸载\n0. 取消\n')
        while True:
            writer.write('请选择 [1/2/0]：')
            writer.flush()
            try:
                answer = reader.readline()
            except KeyboardInterrupt:
                return 'cancel'
            if not answer:
                return 'cancel'
            if answer.strip() in ('1', '升级'):
                return 'upgrade'
            if answer.strip() in ('2', '卸载'):
                return 'uninstall'
            if answer.strip() in ('0', '取消'):
                return 'cancel'
            writer.write('请输入 1、2 或 0。\n')


def main(argv=None, *, announce=True):
    parser = argparse.ArgumentParser(description="Install the SPTL helper; choose upgrade or uninstall when installed")
    # Accept old commands without reinstalling widgets or restarting the panel.
    parser.add_argument("--plasma", choices=("5", "6"), help=argparse.SUPPRESS)
    parser.add_argument("--reload-plasma", action="store_true", help=argparse.SUPPRESS)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--upgrade", action="store_true", help="Install or upgrade without an interactive menu")
    action_group.add_argument("--uninstall", action="store_true")
    parser.add_argument("--purge", action="store_true", help="Also remove saved shared settings")
    parser.add_argument("--splayer-config", help="SP app-data/config/settings.json")
    parser.add_argument("--splayer-command", help="Launch command, e.g. '/path/SPlayer-Next.AppImage'")
    args = parser.parse_args(argv)
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    install = data / "sptl"
    unit = config / "systemd/user/sptl-bridge.service"
    if args.purge and not args.uninstall:
        parser.error("--purge requires --uninstall")
    existing = (install / "helper").is_dir() or unit.exists() or unit.is_symlink()
    action = "uninstall" if args.uninstall else "upgrade"
    if existing and not (args.upgrade or args.uninstall):
        action = choose_installed_action()
    if action == "cancel":
        print("已取消，未修改安装。")
        return
    if action == "uninstall":
        if not existing:
            if args.purge:
                saved = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sptl"
                if saved.is_dir():
                    shutil.rmtree(saved)
            print("No SPTL helper installation found.")
            return
        manager = run("systemctl", "--user", "show-environment", check=False, capture_output=True)
        if manager.returncode:
            parser.error("Cannot connect to the systemd user session")
        if unit.exists() or unit.is_symlink():
            run("systemctl", "--user", "disable", "--now", "sptl-bridge.service")
        unit.unlink(missing_ok=True)
        for path in (install / "helper", install / "shared"):
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        for name in ("LICENSE", "THIRD_PARTY.md"):
            (install / name).unlink(missing_ok=True)
        if install.is_dir() and not any(install.iterdir()):
            install.rmdir()
        if args.purge:
            saved = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sptl"
            if saved.is_dir():
                shutil.rmtree(saved)
        run("systemctl", "--user", "daemon-reload", check=False)
        print("Removed the SPTL helper. Manage the widget and SPlayer plugin in their stores.")
        return
    systemctl = shutil.which("systemctl")
    if not systemctl:
        parser.error("systemctl and a systemd user session are required")
    manager = run(systemctl, "--user", "show-environment", check=False, capture_output=True)
    if manager.returncode:
        parser.error("Cannot connect to the systemd user session; run this installer from your KDE desktop terminal")
    saved = previous_options(unit)
    splayer_config = (args.splayer_config if args.splayer_config is not None
                      else saved.get("splayer_config"))
    splayer_command = (args.splayer_command if args.splayer_command is not None
                       else saved.get("splayer_command"))
    install.mkdir(parents=True, exist_ok=True)
    for directory in ("helper", "shared"):
        target = install / directory
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ROOT / directory, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("LICENSE", "THIRD_PARTY.md"):
        shutil.copy2(ROOT / name, install / name)
    command = [sys.executable, "-m", "sptl.server"]
    if splayer_config:
        command += ["--splayer-config", str(Path(splayer_config).expanduser().resolve())]
    if splayer_command:
        command += ["--splayer-command", *shlex.split(splayer_command)]
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
    if announce:
        print("SPTL helper installed. Get the widget from KDE's Get New Widgets dialog.")
        print("In SPlayer: Global Settings > Plugin Management > Plugin Market > SPTL 任务栏歌词 > Install.")
        print("卸载请再次运行此脚本，并选择「卸载」。")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Operation failed: {shlex.join(error.cmd)} (exit {error.returncode})", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError) as error:
        print(f"Operation failed: {error}", file=sys.stderr)
        sys.exit(1)
