import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import zipfile
import unittest
from unittest.mock import patch, Mock
import setup_downloads as setup

class DownloadTests(unittest.TestCase):
    def archive(self, folder, extra=None):
        path=Path(folder)/'tools.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name in ('adb.exe','AdbWinApi.dll','AdbWinUsbApi.dll'):
                z.writestr('platform-tools/'+name,b'test')
            if extra: z.writestr(extra,b'test')
        return path
    def test_extracts_expected_folder_without_manual_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            adb=setup.unpack_platform_tools(self.archive(folder),Path(folder)/'Sdk')
            self.assertEqual(adb,Path(folder)/'Sdk/platform-tools/adb.exe')
            self.assertTrue(adb.is_file())
    def test_rejects_escape_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                setup.unpack_platform_tools(self.archive(folder,'platform-tools/../../escape'),Path(folder)/'Sdk')
            self.assertFalse((Path(folder)/'Sdk').exists())
    def test_rejects_incomplete_download(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.zip'
            with zipfile.ZipFile(path,'w') as z: z.writestr('platform-tools/adb.exe',b'x')
            with self.assertRaises(RuntimeError): setup.unpack_platform_tools(path,Path(folder)/'Sdk')
    def test_existing_winget_needs_no_download(self):
        with patch.object(setup,'locate_winget',return_value='winget'),patch.object(setup,'download') as download:
            self.assertEqual(setup.ensure_winget(Mock()),'winget')
            download.assert_not_called()
    def test_appinstaller_failure_is_actionable(self):
        with patch.object(setup,'locate_winget',return_value=None),patch.object(setup,'download'),patch.object(setup.subprocess,'run',return_value=Mock(returncode=1)):
            with self.assertRaisesRegex(RuntimeError,'Microsoft Store'): setup.ensure_winget(Mock())
