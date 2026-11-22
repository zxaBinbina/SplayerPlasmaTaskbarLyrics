# SPDX-License-Identifier: AGPL-3.0-only
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
from sptl.environment import Environment


class ActivationTests(unittest.TestCase):
    def test_volume_osd_uses_player_specific_plasma_interface(self):
        environment = Environment()
        with patch.object(environment, "dbus", return_value="()") as dbus:
            environment.show_volume(55)
        dbus.assert_called_once_with("org.kde.osdService.mediaPlayerVolumeChanged", "55", "SPlayer",
                                     "multimedia-player", dest="org.kde.plasmashell", path="/org/kde/osdService")
        with patch.object(environment, "dbus", return_value=""):
            with self.assertRaises(OSError): environment.show_volume(55)

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
