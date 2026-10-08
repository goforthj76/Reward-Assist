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

    def test_relay_failure_still_opens_chrome_with_manual_verification(self):
        with patch.object(self.app, 'find_chrome', return_value=Path('chrome.exe')), \
             patch.object(self.app, 'find_browser_helper', return_value=None), \
             patch.object(self.app, 'start_relay', side_effect=ValueError('Offline')), \
             patch.object(self.app.subprocess, 'Popen') as launch:
            result = self.post('/api/web/start', {'app': 'Taco Bell', 'details':
                'first_name: Alex\nlast_name: Example\nemail: alex@example.com\nzip_code: 75022\nbirthday: 1990-01-01\nEND'})
            self.assertEqual(result[0], 200)
            self.assertEqual(result[1]['submission_url'], '')
            launch.assert_called_once()
            self.assertIn('enter the email code', json.loads((self.session / 'status.json').read_text())['message'])

    def test_next_person_reset_targets_only_selected_taco_app(self):
        with patch.object(self.app, 'clear_android_app_data') as clear:
            result = self.post('/api/taco/reset', {'device_serial': 'chosen-device', 'previous_person_finished': True})
            self.assertEqual(result[0], 200)
            clear.assert_called_once_with('com.tacobell.ordering', 'Taco Bell', 'chosen-device')

    def test_reset_requires_finished_confirmation(self):
        with patch.object(self.app, 'clear_android_app_data') as clear:
            result = self.post('/api/taco/reset', {'device_serial': 'chosen-device'})
            self.assertNotEqual(result[0], 200)
            clear.assert_not_called()

    def test_submission_is_guarded_against_duplicate_attempts(self):
        root = ET.fromstring('<hierarchy><node package="com.tacobell.ordering" text="PLACE ORDER" enabled="true"/></hierarchy>')
        self.app.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        with patch.object(self.app, 'find_adb', return_value='adb'), \
             patch.object(self.app, '_taco_ui', return_value=root), \
             patch.object(self.app, '_taco_tap', return_value=True) as tap:
            self.assertEqual(self.app.submit_taco_order('device')['stage'], 'submission_attempted')
            with self.assertRaisesRegex(ValueError, 'already attempted'):
                self.app.submit_taco_order('device')
            tap.assert_called_once()

    def test_submission_requires_final_screen(self):
        with patch.object(self.app, 'find_adb', return_value='adb'), \
             patch.object(self.app, '_taco_ui', return_value=ET.Element('hierarchy')), \
             patch.object(self.app, '_taco_tap') as tap:
            with self.assertRaisesRegex(ValueError, 'not visible'):
                self.app.submit_taco_order('device')
            tap.assert_not_called()

    def test_payment_listing_is_not_final_confirmation(self):
        root=ET.fromstring('<hierarchy><node package="com.tacobell.ordering" text="Venmo"/><node package="com.tacobell.ordering" text="Select Payment Method"/></hierarchy>')
        self.assertFalse(self.app.payment_ready(root, 'venmo'))
        root=ET.fromstring('<hierarchy><node package="com.tacobell.ordering" text="Venmo"/><node package="com.tacobell.ordering" text="PLACE ORDER"/></hierarchy>')
        self.assertTrue(self.app.payment_ready(root, 'venmo'))
        self.assertFalse(self.app.payment_ready(root, 'gift_card'))

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

    def test_signin_skips_optional_first_run_screens_after_reset(self):
        def intro(title):
            return ET.fromstring('<hierarchy><node package="com.tacobell.ordering" text="'+title+'"/><node package="com.tacobell.ordering" text="Skip This Step For Now"/></hierarchy>')
        def email(value):
            return ET.fromstring('<hierarchy><node text="Email Address"/><node text="NEXT"/><node class="android.widget.EditText" package="com.tacobell.ordering" resource-id="input_field" bounds="[0,0][100,50]" text="'+value+'"/></hierarchy>')
        with patch.object(self.app, 'device_status', return_value={'ok': True}), \
             patch.object(self.app, 'find_adb', return_value='adb'), \
             patch.object(self.app, '_taco_ui', side_effect=[ET.Element('hierarchy'), intro('Share your location'), intro('Share your location'), intro('Never Miss a Craving'), email(''), email('test@example.com')]), \
             patch.object(self.app, '_taco_tap', return_value=True) as tap, \
             patch.object(self.app.subprocess, 'run'), \
             patch.object(self.app.time, 'sleep'):
            self.assertEqual(self.app.start_taco_signin('device', 'test@example.com')['stage'], 'verification_required')
            self.assertEqual([call.kwargs['text'] for call in tap.call_args_list], ['Skip This Step For Now', 'Skip This Step For Now', 'Skip This Step For Now', 'NEXT'])

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

    def test_reward_accessibility_label_uses_clickable_parent(self):
        root = ET.fromstring('<hierarchy><node clickable="true" bounds="[20,600][300,900]"><node text="" content-desc="Cantina Chicken Crispy Taco" bounds="[24,627][294,897]"/></node></hierarchy>')
        with patch.object(self.app, '_taco_ui', return_value=root), \
             patch.object(self.app.subprocess, 'run') as run, \
             patch.object(self.app.time, 'sleep'):
            self.assertTrue(self.app._taco_tap('adb', 'device', text='Cantina Chicken Crispy Taco'))
            self.assertEqual(run.call_args.args[0][-2:], ['160', '750'])

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
