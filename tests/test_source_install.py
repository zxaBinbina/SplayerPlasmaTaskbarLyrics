# SPDX-License-Identifier: AGPL-3.0-only
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import install_source


class SourceInstallerTests(unittest.TestCase):
    def test_running_splayer_stops_before_installing_any_component(self):
        with patch.object(install_source, 'splayer_running', return_value=True), \
             patch.object(install_source.build, 'build') as build, \
             patch.object(install_source.install, 'main') as helper:
            with self.assertRaisesRegex(ValueError, '退出 SPlayer'):
                install_source.main(['--all'])
            build.assert_not_called()
            helper.assert_not_called()

    def test_plasma_detection_does_not_need_a_display(self):
        with patch.object(install_source.install, 'session_environment', return_value={'QT_QPA_PLATFORM': 'wayland'}), \
             patch.object(install_source.shutil, 'which', return_value='/usr/bin/plasmashell'), \
             patch.object(install_source.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'plasmashell 6.8.3', '')) as run:
            self.assertEqual(install_source.detect_plasma(), '6')
            self.assertEqual(run.call_args.kwargs['env']['QT_QPA_PLATFORM'], 'offscreen')
            self.assertEqual(run.call_args.kwargs['timeout'], 10)

    def test_unknown_registry_format_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            app_data = Path(directory)
            registry = app_data / 'plugins/manifest.json'
            registry.parent.mkdir()
            registry.write_text('{"version": 2, "plugins": {"other": {}}}')
            before = registry.read_bytes()
            with self.assertRaises(ValueError):
                install_source.read_registry(app_data)
            self.assertEqual(registry.read_bytes(), before)

    def test_source_entry_point_works_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix='sptl source cwd ') as directory:
            result = subprocess.run(['sh', str(ROOT / 'install-from-source.sh'), '--help'],
                                    cwd=directory, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--all', result.stdout)
            self.assertIn('--helper-only', result.stdout)


if __name__ == '__main__':
    unittest.main()
