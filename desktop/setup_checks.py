"""Read-only prerequisite checks shared by setup and the installed app."""
import os
from pathlib import Path
import shutil
import subprocess


def locate_adb():
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    candidates = [os.environ.get('ADB', ''), shutil.which('adb') or '',
                  str(local / 'Android/Sdk/platform-tools/adb.exe')]
    packages = local / 'Microsoft/WinGet/Packages'
    if packages.is_dir():
        candidates.extend(str(p) for p in packages.glob('Google.PlatformTools_*/platform-tools/adb.exe'))
    return next((Path(p) for p in candidates if p and Path(p).is_file()), None)


def inspect_android(adb):
    def run(*args):
        result = subprocess.run([str(adb), *args], capture_output=True, text=True,
                                timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('Android connection check failed. Reconnect the device and try again.')
        return result.stdout
    run('start-server')
    lines = run('devices').splitlines()
    devices = [line.split()[:2] for line in lines if '\t' in line]
    if not devices:
        return 'No Android device found. Connect a data-capable USB cable, enable USB debugging, and check again.'
    reports = []
    for serial, state in devices:
        if state != 'device':
            reports.append(f'{serial}: {state}. Unlock the device and allow USB debugging; reconnect if offline.')
            continue
        packages = set(run('-s', serial, 'shell', 'pm', 'list', 'packages').splitlines())
        apps = [('Taco Bell', 'com.tacobell.ordering'), ('Dutch Bros', 'com.dutchbros.loyalty'), ('Paris Baguette', 'com.parisbaguette.app')]
        reports.append(f'{serial}: connected and authorized.\n' + '\n'.join(
            f'  {name}: ' + ('installed' if 'package:' + package in packages else 'install from Google Play if you will use it')
            for name, package in apps))
    return '\n\n'.join(reports)
