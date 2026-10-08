import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch


class HouseholdApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        desktop = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(desktop))
        self.addCleanup(lambda: sys.path.remove(str(desktop)))
        spec = importlib.util.spec_from_file_location('household_test_app', desktop / 'local_app.py')
        self.app = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'LOCALAPPDATA': self.temp.name}):
            spec.loader.exec_module(self.app)
        self.session = self.app.WEB_SESSION_ROOT / 'taco-bell'
        self.session.mkdir(parents=True)
        self.task = self.session / 'task.json'

    def post(self, path, payload):
        handler = Mock(path=path)
        handler.read_json.return_value = payload
        self.app.Handler.do_POST(handler)
        return handler.send_json.call_args.args

    def test_cancel_stops_task_and_ignores_late_completion(self):
        self.task.write_text(json.dumps({'active': True, 'details': {'email': 'first@example.com'}}))
        self.assertEqual(self.post('/api/web/cancel', {'app': 'Taco Bell'})[0], 200)
        self.assertFalse(json.loads(self.task.read_text())['active'])
        result = self.post('/api/extension/status', {'app': 'Taco Bell', 'stage': 'complete',
                                                   'details': {'email': 'first@example.com'}})
        self.assertTrue(result[1]['ignored'])
        self.assertEqual(json.loads((self.session / 'status.json').read_text())['stage'], 'idle')

    def test_previous_person_cannot_complete_current_signup(self):
        self.task.write_text(json.dumps({'active': True, 'details': {'email': 'second@example.com'}}))
        result = self.post('/api/extension/status', {'app': 'Taco Bell', 'stage': 'complete',
                                                   'details': {'email': 'first@example.com'}})
        self.assertTrue(result[1]['ignored'])
        self.assertTrue(json.loads(self.task.read_text())['active'])

    def test_android_signin_enters_email_then_requests_verification(self):
        def screen(email):
            return ET.fromstring('<hierarchy><node text="Email Address"/><node text="NEXT"/>'
                                '<node class="android.widget.EditText" package="com.tacobell.ordering" '
                                'resource-id="input_field" bounds="[16,661][584,709]" text="'+email+'"/></hierarchy>')
        with patch.object(self.app, 'device_status', return_value={'ok': True}), \
             patch.object(self.app, 'find_adb', return_value='adb'), \
             patch.object(self.app, '_taco_ui', side_effect=[screen(''), screen('test@example.com')]), \
             patch.object(self.app, '_taco_tap', return_value=True) as tap, \
             patch.object(self.app.subprocess, 'run') as run, \
             patch.object(self.app.time, 'sleep'):
            result = self.app.start_taco_signin('device', 'test@example.com')
            self.assertEqual(result['stage'], 'verification_required')
            tap.assert_called_once_with('adb', 'device', text='NEXT')
            self.assertTrue(any(call.args[0][-2:] == ['text', 'test@example.com'] for call in run.call_args_list))

    def test_android_signin_stops_on_unrecognized_form(self):
        with patch.object(self.app, 'device_status', return_value={'ok': True}), \
             patch.object(self.app, 'find_adb', return_value='adb'), \
             patch.object(self.app, '_taco_ui', return_value=ET.Element('hierarchy')), \
             patch.object(self.app, '_taco_tap', return_value=False), \
             patch.object(self.app.subprocess, 'run') as run, \
             patch.object(self.app.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'email Sign In screen'):
                self.app.start_taco_signin('device', 'test@example.com')
            self.assertEqual(run.call_count, 1)  # Launch only; no credential entry.

    def test_pickup_selects_top_result_not_xml_order(self):
        root = ET.fromstring('<hierarchy><node text="PICKUP HERE" clickable="true" bounds="[0,600][100,650]"/>'
                             '<node text="PICKUP HERE" clickable="true" bounds="[0,200][100,250]"/></hierarchy>')
        with patch.object(self.app, '_taco_ui', return_value=root), \
             patch.object(self.app.subprocess, 'run') as run, \
             patch.object(self.app.time, 'sleep'):
            self.assertTrue(self.app._taco_tap('adb', 'device', text='PICKUP HERE', topmost=True))
            self.assertEqual(run.call_args.args[0][-2:], ['50', '225'])


if __name__ == '__main__':
    unittest.main()
