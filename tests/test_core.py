# SPDX-License-Identifier: AGPL-3.0-only
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
from sptl.environment import Environment
from sptl.local_storage import read_preferences, snappy, table_records
from sptl.model import DEFAULTS, State, normalize_lines, validate_settings


def snapshot(**extra):
    return dict(protocol=1, session="test", settings=DEFAULTS, locale="en-US",
                lyricRevision=1, lines=[], track={"id": "one", "title": "One", "artists": [{"name": "Singer"}]},
                playback={"state": "paused", "position": 500, "duration": 10000, "speed": 1, "timestamp": 1000},
                **extra)


def vint(number):
    out = bytearray()
    while number >= 128:
        out.append((number & 127) | 128)
        number >>= 7
    out.append(number)
    return bytes(out)


def wal(sequence, pairs):
    batch = struct.pack("<QI", sequence, len(pairs))
    for key, value in pairs:
        batch += bytes([int(value is not None)]) + vint(len(key)) + key
        if value is not None:
            batch += vint(len(value)) + value
    return b"\0" * 4 + struct.pack("<HB", len(batch), 1) + batch


def block(pairs):
    data = b""
    for key, value in pairs:
        data += vint(0) + vint(len(key)) + vint(len(value)) + key + value
    return data + struct.pack("<II", 0, 1)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.state = State(clock=lambda: self.now)

    def test_settings_are_bounded_and_shared(self):
        settings = validate_settings({"fontSize": float("nan"), "maxWidth": 5, "manualAccent": "javascript:bad", "lyricMode": "single"})
        self.assertEqual(settings["fontSize"], DEFAULTS["fontSize"])
        self.assertEqual(settings["maxWidth"], 180)
        self.assertEqual(settings["lyricMode"], "single")
        self.assertEqual(settings["manualAccent"], DEFAULTS["manualAccent"])

    def test_absolute_volume_is_validated_independently_of_wheel_steps(self):
        self.state.exchange(snapshot())
        for value, expected in ((0, 0), (0.6, 0.6), (2, 1), (-2, 0)):
            self.state.command("setVolume", value)
            self.assertEqual(self.state.commands[-1]["value"], expected)
        for value in (True, None, "0.5", float("nan")):
            with self.assertRaises(ValueError): self.state.command("setVolume", value)

    def test_pending_liked_start_survives_handshake_once_and_expires(self):
        self.state.pending_start = self.now
        response = self.state.exchange(snapshot(startAvailable=True))
        self.assertEqual([c["action"] for c in response["commands"]], ["startLiked"])
        self.assertIsNone(self.state.pending_start)
        self.state.exchange(snapshot(startAvailable=True, ack=[response["commands"][0]["id"]]))
        self.assertEqual(self.state.commands, [])
        self.state.pending_start = self.now
        self.now += 46
        response = self.state.exchange(dict(snapshot(startAvailable=True), session="new"))
        self.assertEqual(response["commands"], [])

    def test_old_plugin_reports_unavailable_liked_start(self):
        self.state.pending_start = self.now
        self.state.exchange(snapshot())
        self.assertEqual(self.state.command_error, "start_unavailable")
        with self.assertRaises(ValueError): self.state.command("startLiked")

    def test_legacy_plugin_settings_import_only_once(self):
        data = snapshot()
        data["settings"] = dict(DEFAULTS, fontSize=20)
        self.state.exchange(data)
        self.assertEqual(self.state.settings["fontSize"], 20)
        self.state.settings = dict(self.state.settings, fontSize=24)
        data["session"] = "old-plugin-restarted"
        self.state.exchange(data)
        self.assertEqual(self.state.settings["fontSize"], 24)
        restored = State(settings=self.state.settings)
        restored.exchange(data)
        self.assertEqual(restored.settings["fontSize"], 24)

    def test_new_plugin_does_not_reset_saved_settings(self):
        self.state = State(settings=dict(DEFAULTS, fontSize=22, offlineDisplay="hidden"))
        data = snapshot()
        data.pop("settings")
        self.state.exchange(data)
        self.assertEqual(self.state.settings["fontSize"], 22)
        self.assertEqual(self.state.settings["offlineDisplay"], "hidden")

    def test_pause_and_resume_are_distinct_from_idle(self):
        self.state.exchange(snapshot())
        self.assertTrue(self.state.connected)
        self.assertEqual(self.state.content()["track"]["artists"], "Singer")
        self.assertEqual(self.state.playback["state"], "paused")
        data = snapshot()
        data["track"] = None
        self.state.exchange(data)
        self.assertIsNone(self.state.content()["track"])

    def test_command_retries_ack_expiry_and_reconnect(self):
        data = snapshot()
        self.state.exchange(data)
        command_id = self.state.command("next")
        self.assertEqual(self.state.exchange(data)["commands"][0]["id"], command_id)
        self.assertEqual(self.state.exchange(data)["commands"][0]["id"], command_id)
        data["ack"] = [command_id]
        self.assertEqual(self.state.exchange(data)["commands"], [])
        self.state.command("prev")
        self.now = 3.1
        self.assertEqual(self.state.exchange(data)["commands"], [])
        self.state.command("toggle")
        data["session"] = "restarted"
        self.assertEqual(self.state.exchange(data)["commands"], [])

    def test_disconnection_freezes_and_rejects_commands(self):
        self.state.exchange(snapshot())
        self.now = 5
        self.assertFalse(self.state.connected)
        self.assertIsNone(self.state.content()["track"])
        with self.assertRaises(ValueError):
            self.state.command("next")

    def test_invalid_payload_does_not_replace_good_state(self):
        self.state.exchange(snapshot())
        before = self.state.content()
        data = snapshot()
        data["lines"] = "bad"
        with self.assertRaises(ValueError):
            self.state.exchange(data)
        self.assertEqual(self.state.content(), before)

    def test_restart_requests_lyrics_and_track_change_clears_old_lines(self):
        data = snapshot()
        data["lines"] = [{"words": [{"word": "Hello"}], "startTime": 100}]
        self.assertFalse(self.state.exchange(data)["needLines"])
        data.pop("lines")
        self.assertTrue(State().exchange(data)["needLines"])
        data["track"]["id"] = "two"
        self.assertTrue(self.state.exchange(data)["needLines"])
        self.assertEqual(self.state.lines, [])

    def test_timing_is_not_invented(self):
        lines = normalize_lines([
            {"words": [{"word": "Untimed"}]},
            {"words": [{"word": "Line", "startTime": 100, "endTime": 200}], "startTime": 100},
            {"words": [{"word": "Ka", "startTime": 100, "endTime": 150}, {"word": "ra", "startTime": 150, "endTime": 200}],
             "startTime": 100, "translatedLyric": "Translation", "romanLyric": "Roman"}
        ])
        self.assertFalse(lines[0]["timed"])
        self.assertFalse(lines[1]["wordTimed"])
        self.assertTrue(lines[2]["wordTimed"])
        self.assertEqual(lines[2]["text"], "Kara")
        self.assertEqual(lines[2]["romanLyric"], "Roman")

    def test_mode_queue_roundtrip_and_stale_selection(self):
        data = snapshot()
        data["modeAvailable"] = True
        data["playback"].update(repeat="one", shuffle="on")
        data["queue"] = dict(available=True, tracks=[data["track"]], total=1, currentIndex=0, offset=0, requestId=10)
        self.state.exchange(data)
        self.assertEqual(self.state.playback["repeat"], "one")
        self.assertEqual(self.state.playback["shuffle"], "on")
        self.state.command("mode", "list")
        self.state.command("queue", -1)
        self.state.command("queuePlay", {"index": 0, "id": "one", "source": "", "path": ""})
        for action, value in (("mode", "bad"), ("queue", True), ("queue", -2),
                              ("queuePlay", {"index": 0, "id": "another"})):
            with self.assertRaises(ValueError): self.state.command(action, value)
        before = self.state.content()
        data["queue"]["tracks"] = [None]
        with self.assertRaises(ValueError): self.state.exchange(data)
        self.assertEqual(self.state.content(), before)

    def test_legacy_plugin_and_reconnect_clear_extended_controls(self):
        data = snapshot()
        data["queue"] = dict(available=True, tracks=[data["track"]], total=1, currentIndex=0, offset=0)
        data["modeAvailable"] = True
        self.state.exchange(data)
        self.now = 5
        self.assertFalse(self.state.content()["queue"]["available"])
        self.state.exchange(snapshot() | {"session": "legacy"})
        self.assertFalse(self.state.content()["queue"]["available"])
        self.assertFalse(self.state.mode_available)


class StorageTests(unittest.TestCase):
    def test_wal_latest_sequence_and_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            key = b"_file://\0\x01theme"
            old = b"\x01" + json.dumps({"mode": "light"}).encode()
            new = b"\x00" + json.dumps({"mode": "dark", "customColor": "#abcdef"}).encode("utf-16-le")
            Path(directory, "000001.log").write_bytes(wal(1, [(key, old)]))
            Path(directory, "000002.log").write_bytes(wal(2, [(key, new)]))
            self.assertEqual(read_preferences(directory)["theme"]["mode"], "dark")
            Path(directory, "000003.log").write_bytes(wal(3, [(key, None)]))
            self.assertNotIn("theme", read_preferences(directory))

    def test_sst_record_and_snappy_copy(self):
        key = b"_file://\0\x01theme"
        value = b"\x01" + json.dumps({"mode": "dark"}).encode()
        data_block = block([(key + struct.pack("<Q", (9 << 8) | 1), value)])
        handle = vint(0) + vint(len(data_block))
        data = data_block + b"\0" * 5
        index_offset = len(data)
        index = block([(key, handle)])
        data += index + b"\0" * 5
        footer = vint(0) + vint(0) + vint(index_offset) + vint(len(index))
        data += footer.ljust(40, b"\0") + bytes.fromhex("57fb808b247547db")
        self.assertEqual(list(table_records(data))[0], (9, 1, key, value))
        self.assertEqual(snappy(b"\x09\x08abc\x16\x03\x00"), b"abcabcabc")

    def test_cache_cover_and_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "app-data/config/settings.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}")
            image = root / "app-data/cache/covers/a.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image")
            env = Environment(config=str(config))
            env.config_path = config
            self.assertEqual(env.local_cover("cache://covers/a.png?v=2"), image)
            self.assertIsNone(env.local_cover("cache://covers/%2e%2e/%2e%2e/config/settings.json"))
            self.assertIsNone(env.local_cover("file:///etc/passwd"))
    def test_streaming_cover_uses_current_mpris_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "artwork.jpg"
            image.write_bytes(b"image")
            env = Environment()
            env.bus_name = "org.mpris.MediaPlayer2.splayer_next.instance1"
            env.dbus = lambda *args, **kwargs: "({'mpris:artUrl': <'" + image.as_uri() + "'>},)"
            self.assertEqual(env.local_cover("streaming-cover://image?server=x"), image)
            self.assertIsNone(env.local_cover("file:///etc/passwd"))



if __name__ == "__main__":
    unittest.main()
