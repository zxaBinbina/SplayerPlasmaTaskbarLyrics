# SPDX-License-Identifier: AGPL-3.0-only
"""User-level SPlayer discovery, theme reads, cover resolution and window activation."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .local_storage import read_preferences
from .tray import TrayFavorite

CONFIG_NAMES = ("SPlayer-Next", "splayer-next", "splayer_next")
MPRIS_PREFIX = "org.mpris.MediaPlayer2.splayer_next"


class Environment:
    def __init__(self, config=None, command=None):
        self.config_override = Path(config).expanduser() if config else None
        self.command_override = command
        self.config_path = None
        self.theme = {"available": False}
        self.locale = None
        self.running = False
        self.bus_name = None
        self.preferences_signature = None
        self.preferences = {}
        self.tray = TrayFavorite()
        self.favorite = {"available": False, "liked": False}

    def discover(self):
        if self.config_override:
            return self.config_override
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        roots = [base]
        flatpak = Path.home() / ".var/app"
        if flatpak.is_dir():
            roots.extend(p / "config" for p in flatpak.iterdir() if "splayer" in p.name.lower())
        candidates = [root / name / "app-data/config/settings.json" for root in roots for name in CONFIG_NAMES]
        existing = [p for p in candidates if p.is_file()]
        return max(existing, key=lambda p: p.stat().st_mtime) if existing else None

    @staticmethod
    def dbus(method, *args, dest="org.freedesktop.DBus", path="/org/freedesktop/DBus"):
        if not shutil.which("gdbus"):
            return ""
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", dest, "--object-path", path,
             "--method", method, *args], capture_output=True, text=True, timeout=2, check=False
        )
        return result.stdout if result.returncode == 0 else ""

    def refresh(self):
        self.config_path = self.discover()
        names = ""
        try:
            names = self.dbus("org.freedesktop.DBus.ListNames")
            matches = re.findall(r"'(" + re.escape(MPRIS_PREFIX) + r"[^']*)'", names)
            self.bus_name = sorted(matches)[0] if matches else None
        except (OSError, subprocess.SubprocessError):
            self.bus_name = None
        self.running = bool(self.bus_name)
        item = self.tray.inspect(names)
        self.favorite = {key: item[key] for key in ("available", "liked")}
        if not self.running:
            # MPRIS may be disabled in SP. Inspect only processes owned by this user.
            for proc in Path("/proc").glob("[0-9]*"):
                try:
                    if proc.stat().st_uid != os.getuid():
                        continue
                    executable = (proc / "cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")
                    name = Path(executable).name.lower()
                    if name in ("splayer-next", "splayer_next", "splayer") or (name.startswith("splayer-next-") and name.endswith(".appimage")):
                        self.running = True
                        break
                except OSError:
                    continue
        if self.config_path:
            root = self.config_path.parent.parent.parent
            stores = [root / "Partitions/main/Local Storage/leveldb", root / "Local Storage/leveldb"]
            try:
                signature = tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns)
                                  for directory in stores for p in directory.glob("*")
                                  if p.suffix in (".log", ".ldb", ".sst"))
                if signature != self.preferences_signature:
                    preferences = {}
                    for directory in stores:
                        preferences.update(read_preferences(directory))
                    self.preferences = preferences
                    self.preferences_signature = signature
                settings = self.preferences.get("settings", {})
                self.locale = settings.get("locale")
                theme = self.preferences.get("theme", {})
                if theme:
                    image = theme.get("appearanceStyle") == "image" and bool(theme.get("imageBackground", {}).get("src"))
                    mode = "dark" if image else theme.get("mode", "system")
                    source = theme.get("source", "default")
                    accent = theme.get("customColor", "#fe7971") if source == "custom" else "#fe7971"
                    if source == "cover" and image:
                        accent = theme.get("imageBackgroundColor") or accent
                    self.theme = {"available": source != "cover" or image, "mode": mode,
                                  "accent": accent if re.fullmatch(r"#[0-9a-fA-F]{6}", str(accent)) else "#fe7971",
                                  "source": source}
                else:
                    self.theme = {"available": False}
            except (OSError, ValueError, TypeError):
                self.theme = {"available": False}
        else:
            self.theme = {"available": False}

    def cached_cover(self, cover):
        if not self.config_path or not isinstance(cover, str):
            return None
        try:
            config = json.loads(self.config_path.read_text())
            root = Path(config.get("cache", {}).get("dir") or self.config_path.parent.parent / "cache").expanduser().resolve()
            parsed = urlsplit(cover)
            if parsed.scheme == "cache":
                relative = unquote(parsed.netloc + parsed.path)
            elif parsed.scheme == "cover":
                relative = "covers/" + unquote(parsed.netloc + parsed.path).lstrip("/")
            else:
                return None
            path = (root / relative).resolve()
            if path.is_relative_to(root / "covers") and path.is_file() and path.stat().st_size <= 16 * 1024 * 1024:
                return path
        except (OSError, ValueError, TypeError):
            pass
        return None

    def local_cover(self, cover):
        cached = self.cached_cover(cover)
        if cached:
            return cached
        # SP publishes decoded artwork as a temporary file through MPRIS.
        # This also handles streaming-cover:// URLs that depend on SP credentials.
        if not self.bus_name or not isinstance(cover, str) or not cover.startswith("streaming-cover://"):
            return None
        try:
            metadata = self.dbus("org.freedesktop.DBus.Properties.Get",
                                 "org.mpris.MediaPlayer2.Player", "Metadata",
                                 dest=self.bus_name, path="/org/mpris/MediaPlayer2")
            match = re.search(r"'mpris:artUrl': <'([^']*)'>", metadata)
            parsed = urlsplit(match.group(1)) if match else None
            if parsed and parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
                path = Path(unquote(parsed.path)).resolve()
                stat = path.stat()
                if path.is_file() and stat.st_uid == os.getuid() and stat.st_size <= 16 * 1024 * 1024 and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    return path
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return None

    def toggle_favorite(self):
        self.tray.toggle()

    def activate(self):
        if self.bus_name:
            try:
                if self.dbus("org.mpris.MediaPlayer2.Raise", dest=self.bus_name, path="/org/mpris/MediaPlayer2"):
                    return
            except (OSError, subprocess.SubprocessError):
                pass
        if self.command_override:
            command = self.command_override
        else:
            binary = next((shutil.which(name) for name in ("splayer-next", "SPlayer-Next", "splayer") if shutil.which(name)), None)
            command = [binary] if binary else None
            if not command and shutil.which("gio"):
                data_roots = [Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))]
                data_roots += [Path(p) for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
                data_roots += [Path.home() / ".local/share/flatpak/exports/share", Path("/var/lib/flatpak/exports/share")]
                for base in data_roots:
                    desktop = next((p for p in (base / "applications").glob("*.desktop") if "splayer" in p.name.lower()), None)
                    if desktop:
                        command = ["gio", "launch", str(desktop)]
                        break
        if not command:
            raise ValueError("SPlayer launcher not found; see installation guide")
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
