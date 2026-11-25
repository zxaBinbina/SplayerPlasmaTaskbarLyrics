#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Install real source packages into isolated XDG and SPlayer directories."""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import install_source


def main():
    if not shutil.which('kpackagetool6'):
        raise RuntimeError('kpackagetool6 is required for this source installation check')
    with tempfile.TemporaryDirectory(prefix='sptl source install ') as directory:
        base = Path(directory)
        environment = {'XDG_DATA_HOME': str(base / 'data'), 'XDG_CONFIG_HOME': str(base / 'config'),
                       'XDG_STATE_HOME': str(base / 'state'), 'XDG_CACHE_HOME': str(base / 'cache'),
                       'KDE_SESSION_VERSION': '6', 'QT_QPA_PLATFORM': 'offscreen'}
        calls = []
        def systemctl(*command, **kwargs):
            assert Path(command[0]).name == 'systemctl', command
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)
        with patch.dict(os.environ, environment), patch.object(install_source.install, 'run', systemctl):
            with patch.object(install_source.build, 'build', side_effect=AssertionError('helper-only must not build components')):
                install_source.main(['--helper-only'])
            helper = base / 'data/sptl'
            assert (helper / 'helper/sptl/server.py').is_file()
            assert not (base / 'data/plasma').exists()
            assert not (helper / 'zxaBinbina.sptl.js').exists()

            app_data = base / 'SPlayer test/app-data'
            registry = app_data / 'plugins/manifest.json'
            registry.parent.mkdir(parents=True)
            other = {'id': 'other.plugin', 'version': '9.9.9', 'fileName': 'other.plugin.js'}
            registry.write_text(json.dumps({'version': 1, 'note': 'preserve', 'plugins': {'other.plugin': other}}))
            settings = app_data / 'config/settings.json'
            settings.parent.mkdir()
            settings.write_text('{"plugins":{"enabled":{"zxabinbina.sptl":false},"permissions":{"other.plugin":{"network":false}}}}')
            original_settings = settings.read_bytes()
            shared = base / 'state/sptl/settings.json'
            shared.parent.mkdir(parents=True)
            shared.write_text('{"fontSize": 23}')
            arguments = ['--all', '--plasma', '6', '--splayer-data', str(app_data),
                         '--splayer-config', str(settings), '--splayer-command',
                         shlex.join(['/path with spaces/SPlayer.AppImage', '--flag'])]
            with patch.object(install_source, 'splayer_running', return_value=False):
                install_source.main(arguments)
                widget = base / 'data/plasma/plasmoids/org.kde.plasma.sptl'
                assert (widget / 'contents/ui/main.qml').is_file()
                assert json.loads((widget / 'metadata.json').read_text())['KPlugin']['Version'] == install_source.build.VERSION
                stored = json.loads(registry.read_text())
                entry = stored['plugins']['zxabinbina.sptl']
                script = registry.parent / 'scripts' / entry['fileName']
                assert script.read_bytes() == (ROOT / 'dist/zxaBinbina.sptl.js').read_bytes()
                assert entry['hash'] == hashlib.sha1(script.read_bytes()).hexdigest()
                assert entry['apiLevel'] == 5 and entry['grant'] == ['network', 'control', 'api']
                assert stored['plugins']['other.plugin'] == other and stored['note'] == 'preserve'
                installed_at = entry['installedAt']
                helper_unit = base / 'config/systemd/user/sptl-bridge.service'
                original_unit = helper_unit.read_bytes()
                saved = install_source.install.previous_options(helper_unit)
                assert shlex.split(saved['splayer_command']) == ['/path with spaces/SPlayer.AppImage', '--flag']
                # Exercise the interactive choice path through the same full native upgrade.
                with patch.object(install_source, 'choose_components', return_value='all'):
                    install_source.main(arguments[1:])
                assert helper_unit.read_bytes() == original_unit
                assert json.loads(registry.read_text())['plugins']['zxabinbina.sptl']['installedAt'] == installed_at
                assert settings.read_bytes() == original_settings
                assert shared.read_text() == '{"fontSize": 23}'
                assert not list(registry.parent.rglob('.sptl-source-*'))
                assert not any('plasma-plasmashell.service' in call for call in calls)
            install_source.main(['--uninstall'])
            assert not (helper / 'helper').exists()
            assert widget.exists() and script.exists()
            assert settings.read_bytes() == original_settings
            assert shared.read_text() == '{"fontSize": 23}'
    print('Source helper-only and full native install/upgrade, SPlayer registry, preserved settings and helper removal passed')
    print('SPlayer activation and user services were isolated; the live desktop was not modified')


if __name__ == '__main__':
    main()
