# SPDX-License-Identifier: AGPL-3.0-only
"""Loopback-only HTTP bridge. No third-party Python dependencies."""
import argparse
import copy
import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .environment import Environment
from .model import DEFAULTS, State, validate_settings

PORT = 43827
MAX_BODY = 16 * 1024 * 1024


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address=("127.0.0.1", PORT), environment=None, settings_file=None):
        self.environment = environment or Environment()
        self.settings_file = settings_file
        settings = None
        if settings_file:
            try:
                settings = json.loads(Path(settings_file).read_text())
            except (OSError, ValueError):
                pass
        self.state = State(settings)
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.monitor_stop = threading.Event()
        self.monitor = None
        self.last_connected = False
        super().__init__(address, Handler)

    def poll_environment(self):
        while not self.monitor_stop.is_set():
            try:
                # D-Bus/config IO must never hold the playback HTTP lock.
                self.environment.refresh()
                with self.lock:
                    before = copy.deepcopy(self.state.content())
                    self.state.running = self.environment.running
                    self.state.theme = dict(self.environment.theme)
                    self.state.favorite = dict(getattr(self.environment, "favorite", {"available": False, "liked": False}))
                    if self.environment.locale:
                        self.state.locale = self.environment.locale
                    if before != self.state.content():
                        self.state.content_revision += 1
            except (OSError, ValueError, TypeError):
                pass
            self.monitor_stop.wait(2)

    def serve_forever(self, poll_interval=0.5):
        self.monitor = threading.Thread(target=self.poll_environment, daemon=True)
        self.monitor.start()
        try:
            super().serve_forever(poll_interval)
        finally:
            self.monitor_stop.set()

    def server_close(self):
        self.monitor_stop.set()
        if self.monitor:
            self.monitor.join(timeout=3)
        super().server_close()

    def refresh(self):
        connected = self.state.connected
        if connected != self.last_connected:
            self.state.content_revision += 1
            self.last_connected = connected
        if not connected:
            self.state.commands.clear()

    def persist(self, settings=None):
        if not self.settings_file:
            return
        path = Path(self.settings_file)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state.settings if settings is None else settings, ensure_ascii=False))
        temporary.chmod(0o600)
        temporary.replace(path)

    def update_settings(self, changes):
        if not isinstance(changes, dict) or any(key not in DEFAULTS for key in changes):
            raise ValueError("invalid settings patch")
        settings = validate_settings(dict(self.state.settings, **changes))
        # Commit to disk before publishing, so a failed write leaves state intact.
        self.persist(settings)
        self.state.accept_legacy_settings = False
        if settings != self.state.settings:
            self.state.settings = settings
            self.state.content_revision += 1
        return settings


class Handler(BaseHTTPRequestHandler):
    server_version = "SPTL/0.1"
    timeout = 3

    def log_message(self, *args):
        pass

    def respond(self, status, data, content_type="application/json"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def valid_client(self, client=None):
        port = self.server.server_address[1]
        if self.headers.get("Host") != f"127.0.0.1:{port}":
            return False
        # Browser pages cannot read a capability or submit commands cross-origin.
        origin = self.headers.get("Origin")
        if origin and origin not in ("null", f"http://127.0.0.1:{port}"):
            return False
        if client and self.headers.get("X-SPTL-Client") != client:
            return False
        return self.headers.get("Sec-Fetch-Site") not in ("cross-site", "same-site")

    def do_GET(self):
        if not self.valid_client():
            return self.respond(403, {"error": "invalid client"})
        parsed = urlsplit(self.path)
        with self.server.lock:
            self.server.refresh()
            if parsed.path == "/state":
                query = parse_qs(parsed.query)
                revision = str(self.server.state.content_revision)
                state = self.server.state
                result = {"protocol": 1, "revision": state.content_revision,
                          "token": self.server.token, "playback": state.playback,
                          "serverTime": int(time.time() * 1000)}
                if query.get("revision", ["-1"])[0] != revision:
                    result["content"] = state.content()
                # A disconnected player must not keep interpolating old progress.
                if not state.connected:
                    result["playback"] = dict(state.playback, state="stopped")
                return self.respond(200, result)
            if parsed.path == "/cover":
                if parse_qs(parsed.query).get("token", [""])[0] != self.server.token:
                    return self.respond(403, {"error": "invalid capability"})
                path = self.server.environment.local_cover((self.server.state.track or {}).get("cover", ""))
                if path:
                    try:
                        return self.respond(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/jpeg")
                    except OSError:
                        pass
                return self.respond(404, {"error": "cover unavailable"})
        self.respond(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlsplit(self.path)
        client = "plugin" if parsed.path == "/exchange" else "plasma"
        if not self.valid_client(client):
            return self.respond(403, {"error": "invalid client"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.respond(415, {"error": "expected JSON"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.respond(413, {"error": "body too large or empty"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("expected an object")
            with self.server.lock:
                if parsed.path == "/exchange":
                    if self.server.environment.locale:
                        data["locale"] = self.server.environment.locale
                    before = dict(self.server.state.settings)
                    result = self.server.state.exchange(data)
                    if before != self.server.state.settings:
                        self.server.persist()
                    return self.respond(200, result)
                if parsed.path in ("/command", "/settings"):
                    if not secrets.compare_digest(str(data.get("token", "")), self.server.token):
                        return self.respond(403, {"error": "invalid capability"})
                    if parsed.path == "/settings":
                        settings = self.server.update_settings(data.get("settings"))
                        return self.respond(200, {"protocol": 1, "settings": settings})
                    action = data.get("action")
                    if action == "startLiked" and not self.server.state.connected:
                        self.server.state.pending_start = self.server.state.clock()
                    elif action in ("launch", "open"):
                        pass
                    elif action == "favorite":
                        state = self.server.state
                        value = data.get("value")
                        if not state.connected or not state.track or not isinstance(value, dict) or any(
                            value.get(key, "") != state.track[key] for key in ("id", "source", "path")
                        ):
                            raise ValueError("favorite track is stale")
                    else:
                        command_id = self.server.state.command(action, data.get("value"))
                        return self.respond(200, {"id": command_id})
            if parsed.path == "/command" and action in ("launch", "open", "startLiked"):
                # A startup request survives the first plugin session handshake.
                # Window activation must not block playback snapshots.
                try:
                    self.server.environment.activate()
                except (OSError, ValueError):
                    if action == "startLiked":
                        with self.server.lock: self.server.state.pending_start = None
                    raise
                return self.respond(200, {"ok": True})
            if parsed.path == "/command" and action == "favorite":
                # D-Bus must not block playback snapshots behind the state lock.
                self.server.environment.toggle_favorite()
                return self.respond(200, {"ok": True})
            return self.respond(404, {"error": "not found"})
        except (ValueError, TypeError, OverflowError) as error:
            self.respond(400, {"error": str(error)})
        except OSError:
            self.respond(503, {"error": "local operation failed"})


def main():
    parser = argparse.ArgumentParser(description="SPlayer Plasma Taskbar Lyrics bridge")
    parser.add_argument("--splayer-config", help="Path to SP app-data/config/settings.json")
    parser.add_argument("--splayer-command", nargs="+", help="Executable and arguments for launching SP")
    args = parser.parse_args()
    data = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sptl/settings.json"
    server = BridgeServer(environment=Environment(args.splayer_config, args.splayer_command), settings_file=data)
    print(f"SPTL bridge listening on 127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
