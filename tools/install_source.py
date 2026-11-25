#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Install this checkout's helper, optionally its Plasma widget and SPlayer plugin."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import build
import install

APPLET = "org.kde.plasma.sptl"


def choose_components():
    with open('/dev/tty', 'r', encoding='utf-8') as reader, open('/dev/tty', 'w', encoding='utf-8') as writer:
        writer.write('从当前源码安装 SPTL：\n1. 仅安装或升级辅助程序\n'
                     '2. 安装或升级全部组件（辅助程序、KDE 小组件、SPlayer 插件）\n'
                     '3. 卸载辅助程序\n0. 取消\n')
        while True:
            writer.write('请选择 [1/2/3/0]：')
            writer.flush()
            try:
                answer = reader.readline()
            except KeyboardInterrupt:
                return 'cancel'
            if not answer:
                return 'cancel'
            if answer.strip() in ('1', '2', '3', '0'):
                return {'1': 'helper', '2': 'all', '3': 'uninstall', '0': 'cancel'}[answer.strip()]
            writer.write('请输入 1、2、3 或 0。\n')


def detect_plasma():
    environment = install.session_environment()
    version = environment.get('KDE_SESSION_VERSION')
    if version in ('5', '6'):
        return version
    executable = shutil.which('plasmashell')
    if not executable:
        raise ValueError('无法检测 Plasma 版本，请指定 --plasma 5 或 --plasma 6。')
    environment['QT_QPA_PLATFORM'] = 'offscreen'
    result = subprocess.run([executable, '--version'], env=environment, text=True,
                            capture_output=True, check=False, timeout=10)
    match = re.search(r'\bplasmashell\s+(5|6)\.', result.stdout + '\n' + result.stderr)
    if result.returncode or not match:
        raise ValueError('无法检测 Plasma 版本，请指定 --plasma 5 或 --plasma 6。')
    return match.group(1)


def splayer_running():
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            name = (process / 'exe').resolve(strict=True).name
            if re.sub(r'[^a-z0-9]', '', name.lower()) in ('splayernext', 'splayernextexe'):
                return True
        except (OSError, RuntimeError):
            continue
    return False


def app_data_directory(args):
    if args.splayer_data:
        return Path(args.splayer_data).expanduser().resolve()
    settings = args.splayer_config
    if not settings:
        config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        settings = install.previous_options(config / 'systemd/user/sptl-bridge.service').get('splayer_config')
    if settings:
        settings = Path(settings).expanduser().resolve()
        if settings.parent.name != 'config':
            raise ValueError('请提供 app-data/config/settings.json，或用 --splayer-data 指定 app-data 目录。')
        return settings.parent.parent
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    candidates = [config / name / 'app-data' for name in ('SPlayer-Next', 'splayer-next', 'splayer_next')]
    existing = [path for path in candidates if path.is_dir()]
    return max(existing, key=lambda path: path.stat().st_mtime) if existing else candidates[0]


def read_registry(app_data):
    path = app_data / 'plugins/manifest.json'
    if not path.exists():
        return {'version': 1, 'plugins': {}}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('plugins'), dict):
        raise ValueError('无法识别 SPlayer 插件登记文件，请通过官方插件管理导入测试脚本。')
    return data


def plugin_manifest(source):
    block = re.match(r'\s*/\*[\s\S]*?\*/', source)
    if not block:
        raise ValueError('构建的 SPlayer 插件缺少元数据。')
    headers = dict(re.findall(r'^\s*\*?\s*@(\w+)\s+(.+)$', block.group(), re.MULTILINE))
    plugin_id = re.sub(r'[^a-z0-9._-]', '-', headers['id'].strip().lower()).strip('-._')[:64]
    if plugin_id != build.PLUGIN_ID.lower():
        raise ValueError('构建的插件 ID 与 SPTL 不匹配。')
    manifest = {key: headers[key].strip() for key in ('name', 'version', 'author', 'description', 'homepage', 'updateUrl')}
    manifest.update(id=plugin_id, fileName=plugin_id + '.js', apiLevel=int(headers['apiLevel']),
                    grant=list(dict.fromkeys(['network', *headers['grant'].split()])),
                    hash=hashlib.sha1(source.encode('utf-8')).hexdigest(), installedAt=int(time.time() * 1000))
    return manifest


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.sptl-source-', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install_splayer_plugin(source_path, app_data):
    if splayer_running():
        raise ValueError('请先完全退出 SPlayer，再安装源码测试插件。')
    source = source_path.read_text()
    manifest = plugin_manifest(source)
    registry = read_registry(app_data)
    previous = registry['plugins'].get(manifest['id'], {})
    if not isinstance(previous, dict):
        raise ValueError('现有 SPTL 插件登记信息无效，未覆盖。')
    manifest['installedAt'] = previous.get('installedAt', manifest['installedAt'])
    manifest['updatedAt'] = int(time.time() * 1000)
    registry['plugins'][manifest['id']] = {**previous, **manifest}
    script = app_data / 'plugins/scripts' / manifest['fileName']
    atomic_write(script, source.encode('utf-8'))
    atomic_write(app_data / 'plugins/manifest.json', (json.dumps(registry, ensure_ascii=False, indent=2) + '\n').encode())
    return script


def install_widget(package_tool, package):
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    root = data / 'plasma/plasmoids'
    root.mkdir(parents=True, exist_ok=True)
    action = '--upgrade' if (root / APPLET).exists() else '--install'
    environment = install.session_environment()
    environment['QT_QPA_PLATFORM'] = 'offscreen'
    subprocess.run([package_tool, '--type', 'Plasma/Applet', '--packageroot', str(root), action, str(package)],
                   env=environment, check=True, timeout=60)


def main(argv=None):
    parser = argparse.ArgumentParser(description='从当前源码安装 SPTL，可选择辅助程序或全部测试组件。')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true', help='构建并安装辅助程序、KDE 小组件和 SPlayer 插件')
    group.add_argument('--helper-only', action='store_true', help='只安装或升级辅助程序')
    group.add_argument('--uninstall', action='store_true', help='只卸载辅助程序，保留小组件、插件和设置')
    parser.add_argument('--plasma', choices=('5', '6'), help='指定测试小组件的 Plasma 主版本')
    parser.add_argument('--splayer-data', help='SPlayer 的 app-data 目录')
    parser.add_argument('--splayer-config', help='SPlayer 的 app-data/config/settings.json')
    parser.add_argument('--splayer-command', help='SPlayer 启动命令或 AppImage 路径')
    parser.add_argument('--reload-plasma', action='store_true', help='安装测试小组件后重载面板')
    args = parser.parse_args(argv)
    mode = 'all' if args.all else 'helper' if args.helper_only else 'uninstall' if args.uninstall else None
    if mode is None:
        try:
            mode = choose_components()
        except OSError as error:
            raise ValueError('没有交互终端，请指定 --all、--helper-only 或 --uninstall。') from error
    if mode == 'cancel':
        print('已取消，未修改安装。')
        return
    if mode == 'uninstall':
        install.main(['--uninstall'])
        return
    helper_args = ['--upgrade']
    for name in ('splayer_config', 'splayer_command'):
        if getattr(args, name):
            helper_args += ['--' + name.replace('_', '-'), getattr(args, name)]
    if args.splayer_data and not args.splayer_config:
        helper_args += ['--splayer-config', str(Path(args.splayer_data).expanduser().resolve() / 'config/settings.json')]
    if mode == 'helper':
        if args.reload_plasma:
            parser.error('--reload-plasma 需要 --all')
        install.main(helper_args)
        return
    if splayer_running():
        raise ValueError('请先完全退出 SPlayer，再安装源码测试插件。')
    app_data = app_data_directory(args)
    read_registry(app_data)
    version = args.plasma or detect_plasma()
    package_tool = shutil.which('kpackagetool' + version)
    if not package_tool:
        raise ValueError(f'请先安装 kpackagetool{version}。')
    systemctl = shutil.which('systemctl')
    if not systemctl or install.run(systemctl, '--user', 'show-environment', check=False).returncode:
        raise ValueError('请在可用的 systemd 用户会话中运行。')
    if args.reload_plasma and install.run(systemctl, '--user', 'is-active', 'plasma-plasmashell.service',
                                         check=False, capture_output=True).returncode:
        raise ValueError('面板服务未运行；不使用 --reload-plasma 安装后，可注销再登录。')
    dist = build.build()
    install.main(helper_args, announce=False)
    install_widget(package_tool, dist / ('plasma' + version) / APPLET)
    script = install_splayer_plugin(dist / (build.PLUGIN_ID + '.js'), app_data)
    if args.reload_plasma:
        install.run(systemctl, '--user', 'restart', 'plasma-plasmashell.service')
    print(f'当前源码的辅助程序、Plasma {version} 小组件和 SPlayer 插件已安装。')
    print(f'SPlayer 测试插件：{script}')
    print('启动 SPlayer 后加载插件；已有启用状态、权限及插件设置保留。')
    print('辅助程序卸载请再次运行此脚本，选择「卸载辅助程序」；小组件和插件通过各自管理界面卸载。')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print('源码安装失败：' + str(error), file=sys.stderr)
        sys.exit(1)
