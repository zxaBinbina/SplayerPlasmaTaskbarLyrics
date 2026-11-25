# SPDX-License-Identifier: AGPL-3.0-only
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
from sptl.environment import Environment


class ActivationTests(unittest.TestCase):
    def test_explicit_favorite_waits_for_the_requested_tray_state(self):
        environment = Environment()
        with patch.object(environment.tray, "inspect", side_effect=[
            {"available": True, "liked": False}, {"available": True, "liked": False}, {"available": True, "liked": True}
        ]), patch.object(environment.tray, "toggle") as toggle:
            environment.set_favorite(True)
        toggle.assert_called_once()
        self.assertTrue(environment.favorite["liked"])
        with patch.object(environment.tray, "inspect", return_value={"available": True, "liked": True}), \
                patch.object(environment.tray, "toggle") as toggle:
            environment.set_favorite(True)
        toggle.assert_not_called()
        with patch.object(environment.tray, "inspect", return_value={"available": False, "liked": False}):
            with self.assertRaises(ValueError): environment.set_favorite(True)

    def test_native_volume_uses_mpris_player_volume_property(self):
        environment = Environment()
        environment.bus_name = "org.mpris.MediaPlayer2.splayer_next.instance1"
        with patch.object(environment, "dbus", return_value="()") as dbus:
            self.assertTrue(environment.set_volume(.55))
        dbus.assert_called_once_with("org.freedesktop.DBus.Properties.Set",
            "org.mpris.MediaPlayer2.Player", "Volume", "<0.550000000>",
            dest=environment.bus_name, path="/org/mpris/MediaPlayer2")
        with patch.object(environment, "dbus", return_value=""):
            self.assertFalse(environment.set_volume(.55))
        with patch.object(environment, "dbus", side_effect=OSError("No media bus")):
            self.assertFalse(environment.set_volume(.55))

    def test_native_volume_discovers_only_the_splayer_mpris_service(self):
        environment = Environment()
        with patch.object(environment, "dbus", side_effect=[
            "(['org.mpris.MediaPlayer2.vlc', 'org.mpris.MediaPlayer2.splayer_next.instance2'],)", "()"
        ]) as dbus:
            self.assertTrue(environment.set_volume(0))
        self.assertEqual(dbus.call_args.kwargs["dest"], "org.mpris.MediaPlayer2.splayer_next.instance2")
        environment.bus_name = None
        with patch.object(environment, "dbus", return_value="(['org.mpris.MediaPlayer2.vlc'],)") as dbus:
            self.assertFalse(environment.set_volume(.55))
        self.assertEqual(dbus.call_count, 1)

    def test_volume_osd_uses_player_specific_plasma_interface(self):
        environment = Environment()
        icon = Path(__file__).resolve().parents[1] / "plasmoid/contents/images/splayer.svg"
        self.assertTrue(icon.is_file())
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"XDG_DATA_HOME": directory}), \
                patch.object(environment, "dbus", return_value="()") as dbus:
            environment.show_volume(55)
        dbus.assert_called_once_with("org.kde.osdService.mediaPlayerVolumeChanged", "55", "SPlayer",
                                     str(icon), dest="org.kde.plasmashell", path="/org/kde/osdService")
        with patch.object(environment, "dbus", return_value=""):
            with self.assertRaises(OSError): environment.show_volume(55)

    def test_volume_osd_uses_installed_splayer_logo_with_theme_fallback(self):
        environment = Environment()
        with tempfile.TemporaryDirectory(prefix="sptl icons ") as directory, \
                patch.dict("os.environ", {"XDG_DATA_HOME": directory}), \
                patch.object(environment, "dbus", return_value="()") as dbus:
            icon = Path(directory) / "plasma/plasmoids/org.kde.plasma.sptl/contents/images/splayer.svg"
            icon.parent.mkdir(parents=True)
            icon.write_bytes((Path(__file__).resolve().parents[1] / "plasmoid/contents/images/splayer.svg").read_bytes())
            environment.show_volume(100)
            self.assertEqual(dbus.call_args.args[3], str(icon))
            with patch("sptl.environment.Path.is_file", return_value=False):
                environment.show_volume(0)
            self.assertEqual(dbus.call_args.args[3], "SPlayer-Next")

    def test_running_player_uses_native_tray_activation(self):
        environment = Environment()
        environment.bus_name = "org.mpris.MediaPlayer2.splayer_next.instance1"
        with patch.object(environment.tray, "activate", return_value=True), patch("sptl.environment.subprocess.Popen") as launch:
            environment.activate()
        launch.assert_not_called()

    def test_acknowledged_mpris_raise_does_not_block_existing_instance_launcher(self):
        environment = Environment(command=["/opt/SPlayer-Next/SPlayer-Next"])
        environment.bus_name = "org.mpris.MediaPlayer2.splayer_next.instance1"
        with patch.object(environment.tray, "activate", return_value=False), patch.object(environment, "dbus", return_value="()") as dbus, patch("sptl.environment.subprocess.Popen") as launch:
            environment.activate()
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0], ["/opt/SPlayer-Next/SPlayer-Next"])
        dbus.assert_not_called()
