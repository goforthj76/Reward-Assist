import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_app

class InstanceTests(unittest.TestCase):
 def test_second_launch_reuses_existing_server(self):
  error=OSError('occupied');error.winerror=10048
  with patch.object(local_app,'ExclusiveThreadingHTTPServer',side_effect=error) as server, patch.object(local_app,'urlopen',return_value=io.BytesIO(b'{"local":true,"version":"0.5.34"}')), patch.object(local_app,'open_local_ui') as ui:
   local_app.main()
   self.assertEqual(server.call_count,1)
   ui.assert_called_once()
   self.assertEqual(local_app.PORT,8768)
 def test_unrelated_server_does_not_open_app(self):
  error=OSError('occupied');error.winerror=10048
  with patch.object(local_app,'ExclusiveThreadingHTTPServer',side_effect=error), patch.object(local_app,'urlopen',return_value=io.BytesIO(b'{}')), patch.object(local_app,'open_local_ui') as ui:
   with self.assertRaises(OSError):local_app.main()
   ui.assert_not_called()
