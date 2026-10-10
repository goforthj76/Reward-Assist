"""Official prerequisite downloads; no global PATH or security-setting changes."""
import base64
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from urllib.request import urlopen
import zipfile

PLATFORM_URL = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'
APP_INSTALLER_URL = 'https://aka.ms/getwinget'


def download(url, destination):
    with urlopen(url, timeout=60) as response, Path(destination).open('wb') as output:
        if not response.geturl().startswith('https://'):
            raise RuntimeError('Download redirected to an insecure address.')
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 250 * 1024 * 1024:
                raise RuntimeError('Prerequisite download exceeds the expected size.')
            output.write(chunk)


def unpack_platform_tools(archive, sdk_root):
    sdk_root = Path(sdk_root).resolve()
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                    or ':' in item.filename or not path.parts or path.parts[0] != 'platform-tools'
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise RuntimeError('Invalid Platform-Tools archive path.')
        required = {'platform-tools/adb.exe', 'platform-tools/AdbWinApi.dll', 'platform-tools/AdbWinUsbApi.dll'}
        if not required.issubset(bundle.namelist()) or sum(i.file_size for i in bundle.infolist()) > 500 * 1024 * 1024:
            raise RuntimeError('Platform-Tools download is incomplete or invalid.')
        with tempfile.TemporaryDirectory(prefix='reward-adb-') as folder:
            bundle.extractall(folder)
            target = sdk_root / 'platform-tools'
            if sdk_root.is_symlink() or target.is_symlink():
                raise RuntimeError('Android tools destination is a symbolic link; select a standard installation.')
            shutil.copytree(Path(folder) / 'platform-tools', target, dirs_exist_ok=True)
    return sdk_root / 'platform-tools' / 'adb.exe'


def install_adb(status):
    status('Downloading Android Platform-Tools from Google…')
    with tempfile.TemporaryDirectory(prefix='reward-download-') as folder:
        archive = Path(folder) / 'platform-tools.zip'
        download(PLATFORM_URL, archive)
        status('Extracting Android tools—no manual folder setup needed…')
        adb = unpack_platform_tools(archive, Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk')
    result = subprocess.run([str(adb), 'version'], capture_output=True, text=True, timeout=20,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode or 'Android Debug Bridge' not in result.stdout:
        raise RuntimeError('ADB was extracted but Windows could not run it. See setup diagnostics; do not disable security software.')
    return adb


def locate_winget():
    found = shutil.which('winget')
    alias = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft/WindowsApps/winget.exe'
    return found or (str(alias) if alias.is_file() else None)


def ensure_winget(status):
    existing = locate_winget()
    if existing:
        return existing
    status('Installing Microsoft App Installer for the missing Chrome dependency…')
    with tempfile.TemporaryDirectory(prefix='reward-winget-') as folder:
        bundle = Path(folder) / 'AppInstaller.msixbundle'
        download(APP_INSTALLER_URL, bundle)
        script = "$ErrorActionPreference='Stop'; Add-AppxPackage -Path '" + str(bundle).replace("'", "''") + "'"
        encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                                capture_output=True, text=True, timeout=300,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('Windows could not install Microsoft App Installer automatically. Install or update App Installer from Microsoft Store, then retry. Windows may require additional dependencies or administrator approval.')
    found = locate_winget()
    if not found:
        raise RuntimeError('App Installer was installed, but WinGet is not available yet. Restart setup or sign out and back into Windows.')
    return found
