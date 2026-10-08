import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
import background_process as bg

class BackgroundTests(unittest.TestCase):
    def test_console_hidden(self):
        with patch.object(bg.subprocess, 'run') as run:
            bg.run_hidden(['adb','devices'], capture_output=True)
            self.assertTrue(run.call_args.kwargs['creationflags'] & bg.subprocess.CREATE_NO_WINDOW)
    def test_browser_minimized_without_activation(self):
        startup=bg.minimized_browser_options()['startupinfo']
        self.assertEqual(startup.wShowWindow,7)
        self.assertTrue(startup.dwFlags & bg.subprocess.STARTF_USESHOWWINDOW)
