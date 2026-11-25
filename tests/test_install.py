# SPDX-License-Identifier: AGPL-3.0-only
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import install


class HelperInstallerTests(unittest.TestCase):
    def test_preserves_explicit_session_address(self):
        explicit = {"XDG_RUNTIME_DIR": "/custom/runtime", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/custom/bus"}
        with patch.dict(os.environ, explicit, clear=True):
            self.assertEqual(install.session_environment(), explicit)

    def test_unavailable_user_manager_stops_before_writing(self):
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["install.py", "--upgrade"]),
            patch.object(install.shutil, "which", return_value="/usr/bin/systemctl"),
            patch.object(install, "run", return_value=subprocess.CompletedProcess([], 1)),
            patch.object(install.shutil, "copytree") as copy,
            contextlib.redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit):
                install.main()
            copy.assert_not_called()
        self.assertIn("KDE desktop terminal", stderr.getvalue())

    def test_missing_systemctl_stops_before_writing(self):
        with (
            patch.object(sys, "argv", ["install.py", "--upgrade"]),
            patch.object(install.shutil, "which", return_value=None),
            patch.object(install.shutil, "copytree") as copy,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit):
                install.main()
            copy.assert_not_called()

    def test_saved_options_keep_spaces_and_systemd_percent_escapes(self):
        with tempfile.TemporaryDirectory() as directory:
            unit = Path(directory) / "bridge.service"
            arguments = ["/usr/bin/python3", "-m", "sptl.server", "--splayer-config",
                         "/path with spaces/50%/settings.json", "--splayer-command",
                         "/path with spaces/SPlayer.AppImage", "--flag", "50%"]
            unit.write_text("ExecStart=" + " ".join(install.unit_quote(value) for value in arguments) + "\n")
            saved = install.previous_options(unit)
            self.assertEqual(saved["splayer_config"], arguments[4])
            self.assertEqual(install.shlex.split(saved["splayer_command"]), arguments[6:])

    def test_malformed_saved_options_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            unit = Path(directory) / "bridge.service"
            for command in ("python3 -m sptl.server --splayer-config",
                            "python3 -m sptl.server --splayer-command"):
                unit.write_text("ExecStart=" + command + "\n")
                with self.assertRaises(ValueError):
                    install.previous_options(unit)


if __name__ == "__main__":
    unittest.main()
