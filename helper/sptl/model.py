# SPDX-License-Identifier: AGPL-3.0-only
"""Validated, transport-independent shared state and an acknowledged command mailbox."""
import copy
import json
import math
import time
from pathlib import Path

PLUGIN_ID = "zxaBinbina.sptl"
SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "shared/settings.json").read_text())
DEFAULTS = {item["key"]: item["default"] for item in SCHEMA}


def empty_queue():
    return {"available": False, "tracks": [], "total": 0, "currentIndex": -1,
            "offset": 0, "requestId": 0, "error": ""}


def finite(value, default=0):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else default


def validate_settings(raw):
    if not isinstance(raw, dict):
        raw = {}
    result = {}
    for item in SCHEMA:
        value = raw.get(item["key"], item["default"])
        if item["type"] == "switch":
            value = value if isinstance(value, bool) else item["default"]
        elif item["type"] == "number":
            value = max(item["min"], min(item["max"], finite(value, item["default"])))
        elif item["type"] == "select":
            value = value if value in [o["value"] for o in item["options"]] else item["default"]
        else:
            import re
            value = value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else item["default"]
        result[item["key"]] = value
    return result


def normalize_lines(raw):
    if not isinstance(raw, list) or len(raw) > 20000:
        raise ValueError("invalid lyrics")
    result = []
    for line in raw:
        if not isinstance(line, dict):
            raise ValueError("invalid lyric line")
        words = line.get("words", [])
        if not isinstance(words, list) or len(words) > 5000:
            raise ValueError("invalid lyric words")
        clean_words = []
        for word in words:
            if not isinstance(word, dict):
                raise ValueError("invalid lyric word")
            clean_words.append({
                "word": str(word.get("word", ""))[:20000],
                "startTime": max(0, finite(word.get("startTime"), -1)),
                "endTime": max(0, finite(word.get("endTime"), -1)),
                "romanWord": str(word.get("romanWord", ""))[:20000],
            })
        start = finite(line.get("startTime"), -1)
        end = finite(line.get("endTime"), -1)
        result.append({
            "words": clean_words, "text": "".join(w["word"] for w in clean_words),
            "translatedLyric": str(line.get("translatedLyric", ""))[:20000],
            "romanLyric": str(line.get("romanLyric", ""))[:20000],
            "startTime": start, "endTime": end,
            "timed": start >= 0,
            "wordTimed": len(clean_words) > 1 and len({w["startTime"] for w in clean_words}) > 1 and
                all(finite(w.get("startTime"), -1) >= 0 and finite(w.get("endTime"), -1) >= finite(w.get("startTime"), -1) for w in words),
            "isBG": bool(line.get("isBG", False)),
        })
    return result


def normalize_track(raw):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("invalid track")
    artists = raw.get("artists", [])
    if isinstance(artists, list):
        artists = " / ".join(str(a.get("name", "")) for a in artists if isinstance(a, dict))
    return {key: str(raw.get(key, ""))[:20000] for key in ("id", "source", "title", "cover", "path")} | {
        "artists": str(artists)[:20000], "duration": max(0, finite(raw.get("duration")))
    }


def normalize_queue(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("tracks"), list) or len(raw["tracks"]) > 100:
        raise ValueError("invalid playback queue")
    result = empty_queue()
    for key in ("total", "offset", "requestId", "currentIndex"):
        value = raw.get(key, result[key])
        if not isinstance(value, int) or isinstance(value, bool) or value < (-1 if key == "currentIndex" else 0):
            raise ValueError("invalid queue index")
        result[key] = value
    result["tracks"] = [normalize_track(track) for track in raw["tracks"]]
    if any(track is None for track in result["tracks"]):
        raise ValueError("invalid queue track")
    result["available"] = raw.get("available") is True
    result["error"] = "unavailable" if raw.get("error") else ""
    return result


class State:
    def __init__(self, settings=None, clock=time.monotonic):
        self.clock = clock
        self.settings = validate_settings(settings)
        self.accept_legacy_settings = settings is None
        self.track = None
        self.lines = []
        self.session = None
        self.lyric_revision = -1
        self.last_seen = -100
        self.running = False
        self.locale = "zh-CN"
        self.theme = {"available": False}
        self.favorite = {"available": False, "liked": False}
        self.queue = empty_queue()
        self.mode_available = False
        self.command_error = ""
        self.start_available = False
        self.fm_active = False
        self.fm_available = False
        self.pending_start = None
        self.content_revision = 0
        self.playback = {"state": "idle", "position": 0, "duration": 0, "speed": 1,
                         "offset": 0, "volume": 1, "index": -1, "timestamp": 0,
                         "repeat": "list", "shuffle": "off"}
        self.commands = []
        self.command_results = []
        self.next_command = 0

    @property
    def connected(self):
        return self.session is not None and self.clock() - self.last_seen < 4

    def content(self):
        return {"settings": self.settings, "track": self.track if self.connected else None,
                "lines": self.lines if self.connected else [], "locale": self.locale,
                "theme": self.theme, "running": self.running or self.connected,
                "favorite": self.favorite, "queue": self.queue if self.connected else empty_queue(),
                "modeAvailable": self.mode_available, "commandError": self.command_error,
                "startAvailable": self.start_available,
                "fmActive": self.connected and self.fm_active, "fmAvailable": self.connected and self.fm_available,
                "pluginConnected": self.connected}

    def exchange(self, data):
        # Validate the whole message before mutating state.
        if data.get("protocol") != 1 or not isinstance(data.get("session"), str) or not 1 <= len(data["session"]) <= 128:
            raise ValueError("unsupported protocol or session")
        raw_playback = data.get("playback")
        if not isinstance(raw_playback, dict):
            raise ValueError("invalid playback")
        revision = data.get("lyricRevision")
        if not isinstance(revision, int) or revision < 0:
            raise ValueError("invalid lyric revision")
        track = normalize_track(data.get("track"))
        # Older SP plugins still send settings. Import them once on a fresh
        # installation; Plasma and the saved shared file own all later edits.
        settings = self.settings
        import_settings = self.accept_legacy_settings and isinstance(data.get("settings"), dict)
        if import_settings:
            settings = validate_settings(data["settings"])
        lines = normalize_lines(data["lines"]) if "lines" in data else None
        queue = normalize_queue(data["queue"]) if "queue" in data else None
        playback = {key: finite(raw_playback.get(key), value) for key, value in self.playback.items()
                    if key not in ("state", "repeat", "shuffle")}
        playback["repeat"] = "one" if raw_playback.get("repeat") == "one" else "list"
        playback["shuffle"] = "on" if raw_playback.get("shuffle") == "on" else "off"
        playback["position"] = max(0, playback["position"])
        playback["duration"] = max(0, playback["duration"])
        playback["speed"] = max(0, min(8, playback["speed"]))
        playback["volume"] = max(0, min(1, playback["volume"]))
        playback["state"] = raw_playback.get("state") if raw_playback.get("state") in ("playing", "paused", "idle", "stopped", "loading") else "idle"
        ack = data.get("ack", [])
        if not isinstance(ack, list) or len(ack) > 1024:
            raise ValueError("invalid acknowledgements")
        results = data.get("results", [])
        if not isinstance(results, list) or len(results) > 1024 or any(
            not isinstance(result, dict) or type(result.get("id")) is not int or
            type(result.get("ok")) is not bool for result in results
        ):
            raise ValueError("invalid command results")
        previous = copy.deepcopy(self.content())
        new_session = data["session"] != self.session
        previous_track = self.track
        if new_session:
            self.commands.clear()
            self.command_results.clear()
            self.lines = []
            self.lyric_revision = -1
            self.queue = empty_queue()
        self.session = data["session"]
        self.last_seen = self.clock()
        self.track = track
        if previous_track and track and any(previous_track[k] != track[k] for k in ("id", "source", "path")):
            self.lines = []
            self.lyric_revision = -1
        if lines is not None:
            self.lines = lines
            self.lyric_revision = revision
        self.settings = settings
        if queue is not None:
            self.queue = queue
        self.mode_available = data.get("modeAvailable") is True
        self.start_available = data.get("startAvailable") is True
        self.fm_active = bool(track and track["source"] == "netease" and data.get("fmActive") is True)
        self.fm_available = data.get("fmAvailable") is True
        self.command_error = data.get("commandError", "") if data.get("commandError") in (
            "control_failed", "queue_changed", "queue_unavailable", "login_required", "liked_empty", "start_unavailable", "fm_changed") else ""
        if import_settings:
            self.accept_legacy_settings = False
        self.playback = playback
        self.locale = str(data.get("locale", "zh-CN"))[:32]
        now = self.clock()
        supplied = {result["id"]: result for result in results}
        for command in self.commands:
            if command["id"] in ack:
                result = supplied.get(command["id"])
                self.complete_command(command["id"], result["ok"] if result else not self.command_error,
                                      result.get("error", "") if result else self.command_error)
        for result in results:
            if 0 < result["id"] <= self.next_command:
                self.complete_command(result["id"], result["ok"], result.get("error", ""))
        self.commands = [c for c in self.commands if c["id"] not in ack and now - c["created"] < 3]
        if self.pending_start is not None:
            requested_at = self.pending_start
            self.pending_start = None
            if now - requested_at < 45:
                if self.start_available:
                    self.command("startLiked")
                else:
                    self.command_error = "start_unavailable"
        if previous != self.content():
            self.content_revision += 1
        return {"protocol": 1, "locale": self.locale, "needLines": self.lyric_revision != revision,
                "commands": [{k: v for k, v in c.items() if k != "created"} for c in self.commands]}

    def complete_command(self, command_id, ok, error=""):
        if any(result["id"] == command_id for result in self.command_results):
            return
        errors = ("control_failed", "queue_changed", "queue_unavailable", "login_required", "liked_empty", "start_unavailable", "fm_changed")
        self.command_results.append({"id": command_id, "ok": ok, "error": error if error in errors else "control_failed" if not ok else ""})
        self.command_results = self.command_results[-128:]

    def command(self, action, value=None):
        if action not in ("prev", "next", "toggle", "seek", "volume", "setVolume", "mode", "queue", "queuePlay", "startLiked", "dislike"):
            raise ValueError("unknown command")
        if not self.connected:
            raise ValueError("plugin disconnected")
        if action == "startLiked" and not self.start_available:
            raise ValueError("liked playback is unavailable; update the SP plugin")
        if action == "toggle" and value not in (None, "playing", "paused"):
            raise ValueError("invalid playback state")
        if action in ("seek", "volume", "setVolume"):
            if finite(value, None) is None:
                raise ValueError("invalid command value")
            value = (max(0, min(value, self.playback["duration"] or value)) if action == "seek" else
                     max(0, min(1, value)) if action == "setVolume" else max(-1, min(1, value)))
        if action == "mode" and (self.fm_active or not self.mode_available or value not in ("list", "one", "shuffle")):
            raise ValueError("invalid or unavailable playback mode")
        if action == "dislike":
            if not self.fm_active or not self.fm_available or not self.track or not isinstance(value, dict) or any(
                value.get(key, "") != self.track[key] for key in ("id", "source", "path")
            ):
                raise ValueError("FM track changed or dislike unavailable")
            value = {key: self.track[key] for key in ("id", "source", "path")}
        if action == "queue" and (not isinstance(value, int) or isinstance(value, bool) or not -1 <= value <= 1000000):
            raise ValueError("invalid queue offset")
        if action == "queuePlay":
            if not isinstance(value, dict) or not isinstance(value.get("index"), int) or isinstance(value["index"], bool):
                raise ValueError("invalid queue selection")
            index = value["index"] - self.queue["offset"]
            if not 0 <= index < len(self.queue["tracks"]) or not self.queue["available"]:
                raise ValueError("queue selection is stale")
            track = self.queue["tracks"][index]
            if any(value.get(key, "") != track[key] for key in ("id", "source", "path")):
                raise ValueError("queue selection is stale")
            value = {key: value.get(key, "") for key in ("index", "id", "source", "path")}
        if len(self.commands) >= 128:
            raise ValueError("command queue full")
        self.next_command += 1
        self.commands.append({"id": self.next_command, "action": action, "value": value, "created": self.clock()})
        return self.next_command
