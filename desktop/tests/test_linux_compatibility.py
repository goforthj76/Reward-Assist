import unittest
import sys
from pathlib import Path

# Add desktop to path
desktop_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(desktop_dir))

import local_app
import setup_checks
import setup_downloads


class TestLinuxCompatibility(unittest.TestCase):
    def test_linux_key_generation(self):
        key = local_app._linux_key()
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 32)

    def test_linux_crypt_roundtrip(self):
        key = local_app._linux_key()
        nonce = b"abcdefghijklmnop"
        data = b'{"email": "test@example.com", "birthday": "2000-01-01"}'
        enc = local_app._linux_crypt(data, key, nonce)
        self.assertNotEqual(enc, data)
        dec = local_app._linux_crypt(enc, key, nonce)
        self.assertEqual(dec, data)

    def test_unprotect_linux_magic(self):
        key = local_app._linux_key()
        nonce = b"1234567890123456"
        data = b"secret payload 42"
        cipher = local_app._linux_crypt(data, key, nonce)
        packet = b"LNX1" + nonce + cipher
        result = local_app.unprotect(packet)
        self.assertEqual(result, data)

    def test_installer_script_exists(self):
        root_installer = desktop_dir.parent / "install-linux.sh"
        self.assertTrue(root_installer.is_file())
        content = root_installer.read_text(encoding="utf-8")
        self.assertIn("reward-assist", content)
        self.assertIn("systemd", content)
        self.assertIn("platform-tools", content)

    def test_run_linux_script_exists(self):
        runner = desktop_dir / "run-linux.sh"
        self.assertTrue(runner.is_file())
        content = runner.read_text(encoding="utf-8")
        self.assertIn("local_app.py", content)


if __name__ == "__main__":
    unittest.main()
