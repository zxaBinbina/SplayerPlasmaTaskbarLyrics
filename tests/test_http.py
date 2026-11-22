# SPDX-License-Identifier: AGPL-3.0-only
import http.client
import json
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
from sptl.server import BridgeServer
from test_core import snapshot


class FakeEnvironment:
    running = False
    theme = {"available": True, "mode": "dark", "accent": "#123456"}
    locale = None
    launched = 0
    favorite = {"available": True, "liked": False}
    favorite_clicks = 0
    def __init__(self):
        self.ready = threading.Event()
        self.volume_osds = []
    def refresh(self): self.ready.set()
    def local_cover(self, cover): return None
    def activate(self): self.launched += 1
    def toggle_favorite(self): self.favorite_clicks += 1
    def show_volume(self, percent): self.volume_osds.append(percent)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.env = FakeEnvironment()
        self.server = BridgeServer(("127.0.0.1", 0), environment=self.env)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.assertTrue(self.env.ready.wait(2))
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        supplied = {"Content-Type": "application/json", "X-SPTL-Client": "plugin" if path == "/exchange" else "plasma"}
        supplied.update(headers or {})
        connection.request(method, path, json.dumps(body) if body is not None else None, supplied)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_complete_data_command_and_revision_roundtrip(self):
        self.assertEqual(self.request("POST", "/exchange", snapshot())[0], 200)
        status, first = self.request("GET", "/state")
        self.assertEqual(status, 200)
        self.assertTrue(first["content"]["pluginConnected"])
        status, second = self.request("GET", "/state?revision=" + str(first["revision"]))
        self.assertNotIn("content", second)
        self.assertIn("playback", second)
        status, result = self.request("POST", "/command", {"token": first["token"], "action": "seek", "value": 2000})
        self.assertEqual(status, 200)
        _, result = self.request("POST", "/exchange", snapshot())
        self.assertEqual(result["commands"][0]["value"], 2000)

    def test_cross_origin_host_and_capability_are_checked(self):
        self.assertEqual(self.request("GET", "/state", headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("GET", "/state", headers={"Host": "example.com"})[0], 403)
        self.assertEqual(self.request("POST", "/command", {"token": "wrong", "action": "launch"})[0], 403)
        self.assertEqual(self.env.launched, 0)

    def test_launch_and_invalid_json_shape(self):
        _, state = self.request("GET", "/state")
        self.assertEqual(self.request("POST", "/command", {"token": state["token"], "action": "launch"})[0], 200)
        self.assertEqual(self.env.launched, 1)
        self.assertEqual(self.request("POST", "/exchange", [1, 2])[0], 400)
        self.assertEqual(self.request("POST", "/command", {"token": state["token"], "action": "unknown"})[0], 400)

    def test_volume_osd_uses_actual_sp_volume_and_requires_connected_authorized_client(self):
        _, state = self.request("GET", "/state")
        body = {"token": state["token"], "action": "volumeOsd", "value": 99}
        self.assertEqual(self.request("POST", "/command", body)[0], 400)
        for volume, percent in ((0, 0), (.555, 56), (1, 100)):
            data = snapshot()
            data["playback"]["volume"] = volume
            self.request("POST", "/exchange", data)
            self.assertEqual(self.request("POST", "/command", dict(body, token="wrong"))[0], 403)
            self.assertEqual(self.request("POST", "/command", body, {"X-SPTL-Client": "plugin"})[0], 403)
            self.assertEqual(self.request("POST", "/command", body)[0], 200)
            self.assertEqual(self.env.volume_osds[-1], percent)
        self.assertEqual(self.server.state.commands, [], "OSD is local, not a player command")
        with patch.object(self.env, "show_volume", side_effect=OSError("OSD unavailable")):
            self.assertEqual(self.request("POST", "/command", body)[0], 503)

    def test_volume_osd_dbus_does_not_block_playback(self):
        self.request("POST", "/exchange", snapshot())
        started, release = threading.Event(), threading.Event()
        def delayed(percent): started.set(); release.wait(3)
        self.env.show_volume = delayed
        worker = threading.Thread(target=lambda: self.request("POST", "/command", {
            "token": self.server.token, "action": "volumeOsd"}))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertEqual(self.request("GET", "/state")[0], 200)
        finally:
            release.set(); worker.join()

    def test_liked_start_launches_then_delivers_after_plugin_connects(self):
        _, state = self.request("GET", "/state")
        body = {"token": state["token"], "action": "startLiked"}
        self.assertEqual(self.request("POST", "/command", dict(body, token="wrong"))[0], 403)
        self.assertIsNone(self.server.state.pending_start)
        self.assertEqual(self.request("POST", "/command", body)[0], 200)
        self.assertEqual(self.env.launched, 1)
        _, response = self.request("POST", "/exchange", snapshot(startAvailable=True))
        self.assertEqual(response["commands"][0]["action"], "startLiked")
        self.assertEqual(self.request("POST", "/command", body)[0], 200)
        self.assertEqual(self.env.launched, 1, "an already connected player does not need to be raised")

    def test_failed_launch_cancels_pending_playback(self):
        _, state = self.request("GET", "/state")
        with patch.object(self.env, "activate", side_effect=ValueError("launcher missing")):
            self.assertEqual(self.request("POST", "/command", {"token": state["token"], "action": "startLiked"})[0], 400)
        self.assertIsNone(self.server.state.pending_start)

    def test_favorite_uses_sp_and_rejects_stale_or_unauthorized_clicks(self):
        self.request("POST", "/exchange", snapshot())
        _, state = self.request("GET", "/state")
        value = {key: state["content"]["track"][key] for key in ("id", "source", "path")}
        body = {"token": state["token"], "action": "favorite", "value": value}
        self.assertEqual(self.request("POST", "/command", dict(body, token="wrong"))[0], 403)
        self.assertEqual(self.request("POST", "/command", dict(body, value=dict(value, id="old")))[0], 400)
        self.assertEqual(self.env.favorite_clicks, 0)
        self.assertEqual(self.request("POST", "/command", body)[0], 200)
        self.assertEqual(self.env.favorite_clicks, 1)
        self.assertEqual(self.server.state.commands, [], "favorites use SP's source-aware tray action")
        with patch.object(self.env, "toggle_favorite", side_effect=ValueError("tray unavailable")):
            self.assertEqual(self.request("POST", "/command", body)[0], 400)

    def test_favorite_dbus_does_not_block_playback_snapshots(self):
        self.request("POST", "/exchange", snapshot())
        _, state = self.request("GET", "/state")
        value = {key: state["content"]["track"][key] for key in ("id", "source", "path")}
        started, release = threading.Event(), threading.Event()
        def delayed(): started.set(); release.wait(3)
        self.env.toggle_favorite = delayed
        worker = threading.Thread(target=lambda: self.request("POST", "/command", {
            "token": state["token"], "action": "favorite", "value": value}))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertEqual(self.request("GET", "/state")[0], 200)
        finally:
            release.set()
            worker.join()
    def test_shared_settings_persist_without_sp_running(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.json"
            self.server.settings_file = settings_file
            _, initial = self.request("GET", "/state")
            status, result = self.request("POST", "/settings", {
                "token": initial["token"], "settings": {"offlineDisplay": "hidden", "fontSize": 24}})
            self.assertEqual(status, 200)
            self.assertEqual(result["settings"]["fontSize"], 24)
            self.assertFalse(self.server.state.connected)
            # Even the previously imported SP plugin cannot undo this Apply.
            self.assertEqual(self.request("POST", "/exchange", snapshot())[0], 200)
            restored = BridgeServer(("127.0.0.1", 0), environment=self.env, settings_file=settings_file)
            try:
                self.assertEqual(restored.state.settings["offlineDisplay"], "hidden")
                self.assertEqual(restored.state.settings["fontSize"], 24)
                self.assertFalse(restored.state.connected)
                self.assertEqual(settings_file.stat().st_mode & 0o777, 0o600)
            finally:
                restored.server_close()

    def test_settings_apply_is_protected_and_updates_all_clients(self):
        _, initial = self.request("GET", "/state")
        body = {"token": initial["token"], "settings": {"fontSize": 22}}
        self.assertEqual(self.request("POST", "/settings", dict(body, token="wrong"))[0], 403)
        self.assertEqual(self.request("POST", "/settings", body, headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("POST", "/settings", body, headers={"X-SPTL-Client": "plugin"})[0], 403)
        self.assertEqual(self.request("POST", "/settings", body)[0], 200)
        self.assertEqual(self.request("POST", "/settings", dict(body, settings={"coverPosition": "right"}))[0], 200)
        for _ in range(2):
            _, state = self.request("GET", "/state?revision=" + str(initial["revision"]))
            self.assertEqual(state["content"]["settings"]["fontSize"], 22)
            self.assertEqual(state["content"]["settings"]["coverPosition"], "right")
        self.assertEqual(self.request("POST", "/settings", dict(body, settings={"unknown": 1}))[0], 400)
        self.assertEqual(self.request("POST", "/settings", dict(body, settings=[]))[0], 400)

    def test_failed_settings_save_leaves_previous_state(self):
        _, initial = self.request("GET", "/state")
        before = dict(self.server.state.settings)
        with patch.object(self.server, "persist", side_effect=OSError("disk unavailable")):
            self.assertEqual(self.request("POST", "/settings", {
                "token": initial["token"], "settings": {"fontSize": 26}})[0], 503)
        self.assertEqual(self.server.state.settings, before)

    def test_slow_environment_io_does_not_block_state_requests(self):
        # Pause the next environment refresh while serving normal HTTP traffic.
        started, release = threading.Event(), threading.Event()
        def slow_refresh():
            started.set()
            release.wait(3)
        self.env.refresh = slow_refresh
        self.server.monitor_stop.set()
        self.server.monitor.join(timeout=3)
        self.server.monitor_stop.clear()
        self.server.monitor = threading.Thread(target=self.server.poll_environment, daemon=True)
        self.server.monitor.start()
        self.assertTrue(started.wait(1))
        try:
            status, _ = self.request("GET", "/state")
            self.assertEqual(status, 200)
        finally:
            release.set()



if __name__ == "__main__":
    unittest.main()
