# SPDX-License-Identifier: AGPL-3.0-only
import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import install


class InstallerDetectionTests(unittest.TestCase):
    def test_detects_without_display_and_overrides_gui_platform(self):
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "wayland"}, clear=True), \
             patch.object(install.shutil, "which", return_value="/usr/bin/plasmashell"), \
             patch.object(install.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "plasmashell 6.8.3\n", "")) as run:
            self.assertEqual(install.detect_plasma(), "6")
            arguments = run.call_args.kwargs
            self.assertEqual(arguments["env"]["QT_QPA_PLATFORM"], "offscreen")
            self.assertTrue(arguments["capture_output"])
            self.assertEqual(arguments["timeout"], 10)

    def test_current_kde_session_version_takes_precedence(self):
        with patch.dict(os.environ, {"KDE_SESSION_VERSION": "5"}, clear=True), \
             patch.object(install.subprocess, "run") as run:
            self.assertEqual(install.detect_plasma(), "5")
            run.assert_not_called()

    def test_abort_produces_actionable_cli_error_before_install(self):
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["install.py"]), \
             patch.object(install, "session_environment", return_value={}), \
             patch.object(install.shutil, "which", return_value="/usr/bin/plasmashell"), \
             patch.object(install.subprocess, "run", return_value=subprocess.CompletedProcess([], -6, "", "")), \
             patch.object(install, "build") as build, contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as error:
                install.main()
            self.assertEqual(error.exception.code, 2)
            build.assert_not_called()
        self.assertIn("--plasma 5 or --plasma 6", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_hung_version_command_is_bounded(self):
        with patch.object(install, "session_environment", return_value={}), \
             patch.object(install.shutil, "which", return_value="/usr/bin/plasmashell"), \
             patch.object(install.subprocess, "run", side_effect=subprocess.TimeoutExpired("plasmashell", 10)):
            with self.assertRaisesRegex(ValueError, "could not run"):
                install.detect_plasma()

    def test_preserves_explicit_session_address(self):
        explicit = {"XDG_RUNTIME_DIR": "/custom/runtime", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/custom/bus"}
        with patch.dict(os.environ, explicit, clear=True):
            self.assertEqual(install.session_environment(), explicit)

    def test_unavailable_user_manager_stops_before_writing(self):
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["install.py", "--plasma", "6"]), \
             patch.object(install.shutil, "which", side_effect=lambda name: "/usr/bin/" + name), \
             patch.object(install, "run", return_value=subprocess.CompletedProcess([], 1)), \
             patch.object(install, "build") as build, contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                install.main()
            build.assert_not_called()
        self.assertIn("KDE desktop terminal", stderr.getvalue())

    def test_reload_requires_a_running_shell_before_installing(self):
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["install.py", "--plasma", "6", "--reload-plasma"]), \
             patch.object(install.shutil, "which", side_effect=lambda name: "/usr/bin/" + name), \
             patch.object(install, "run", side_effect=[subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 3)]), \
             patch.object(install, "build") as build, contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                install.main()
            build.assert_not_called()
        self.assertIn("active plasma-plasmashell.service", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
