import importlib.util
import ast
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock
import xml.etree.ElementTree as ET

with patch('subprocess.run'):
    spec = importlib.util.spec_from_file_location('dutch', Path(__file__).resolve().parents[1] / 'dutch_bros_signup_assistant.py')
    dutch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dutch)

def screen(focus=-1, values=('', '', '')):
    root = ET.Element('hierarchy')
    for i, value in enumerate(values):
        ET.SubElement(root, 'node', {'class': 'android.widget.EditText', 'focused': str(i == focus).lower(), 'text': value, 'bounds': '[0,0][100,100]'})
    return root

class EntryTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(dutch, 'hide_keyboard_if_shown')
        self.hide_ime = patcher.start()
        self.addCleanup(patcher.stop)

    def test_back_only_when_ime_shown(self):
        # Exercise the real function from the source, independent of field tests.
        source = (Path(__file__).resolve().parents[1] / 'dutch_bros_signup_assistant.py').read_text(encoding='utf-8')
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'hide_keyboard_if_shown')
        hide = Mock()
        adb = Mock(return_value='mInputShown=false')
        namespace = {'adb': adb, 'hide_keyboard': hide, 're': __import__('re')}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'dutch.py', 'exec'), namespace)
        namespace['hide_keyboard_if_shown']()
        hide.assert_not_called()
        adb.return_value = 'mInputShown=true'
        namespace['hide_keyboard_if_shown']()
        hide.assert_called_once()

    def test_dashboard_preserves_helper_reason(self):
        source = (Path(__file__).resolve().parents[1] / 'local_app.py').read_text(encoding='utf-8')
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'monitor_dutch_process')
        namespace = {'subprocess': __import__('subprocess'), 'Path': Path, 'json': json, 'dt': dt}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'local_app.py', 'exec'), namespace)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'status.json'
            path.write_text(json.dumps({'stage': 'running', 'message': 'Could not focus field 3.'}))
            namespace['monitor_dutch_process'](Mock(wait=Mock(return_value=1)), {}, path, None)
            status = json.loads(path.read_text())
            self.assertEqual(status['stage'], 'attention')
            self.assertIn('Could not focus field 3.', status['message'])
            self.assertNotIn('window', status['message'])

    def test_wrong_focus_never_clears(self):
        with patch.object(dutch, 'ui_root', side_effect=[screen(), screen(1)]), patch.object(dutch, 'click'), patch.object(dutch, 'replace_focused_text') as replace:
            with self.assertRaisesRegex(SystemExit, 'no text was cleared'):
                dutch.fill_current_field(2, '2025550100', 3, 'Sign Up')
            replace.assert_not_called()

    def test_phone_format_verified(self):
        with patch.object(dutch, 'ui_root', side_effect=[screen(), screen(2), screen(2, ('Practice', 'User', '(202) 555-0100'))]), patch.object(dutch, 'click'), patch.object(dutch, 'replace_focused_text') as replace, patch.object(dutch.time, 'sleep'):
            dutch.fill_current_field(2, '2025550100', 3, 'Sign Up')
            replace.assert_called_once_with('2025550100')

    def test_entry_failure_stops(self):
        with patch.object(dutch, 'ui_root', side_effect=[screen(), screen(2), screen(2)]), patch.object(dutch, 'click'), patch.object(dutch, 'replace_focused_text'), patch.object(dutch.time, 'sleep'):
            with self.assertRaisesRegex(SystemExit, 'did not retain'):
                dutch.fill_current_field(2, '2025550100', 3, 'Sign Up')

    def test_missing_console_still_writes_status(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'status.json'
            mirror = dutch.StatusMirror(None, path)
            mirror.write('Safe failure message\n')
            mirror.flush()
            self.assertEqual(json.loads(path.read_text())['message'], 'Safe failure message')

if __name__ == '__main__':
    unittest.main()
