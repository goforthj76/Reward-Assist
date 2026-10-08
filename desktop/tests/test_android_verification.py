import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
import android_verification as verification


def screen(code='', extra='', valid=True):
    p='com.tacobell.ordering' if valid else 'other.app'
    return ET.fromstring(f'<hierarchy><node package="{p}" text="Verify Your Email"/><node package="{p}" text="Code"/><node package="{p}" text="VERIFY"/><node package="{p}" class="android.widget.EditText" resource-id="input_field" text="{code}" bounds="[0,0][100,50]"/>{extra}</hierarchy>')

class VerificationTests(unittest.TestCase):
    def call_verify(self, screens):
        return verification.verify_android_code('adb','device','001234',Mock(side_effect=screens),self.tap,lambda b:(50,25),lambda *a:list(a))
    def setUp(self):
        self.tap=Mock(return_value=True)
        self.run=patch.object(verification.subprocess,'run').start()
        patch.object(verification.time,'sleep').start()
        self.addCleanup(patch.stopall)
    def test_verified_screen_continues(self):
        signed=ET.fromstring('<hierarchy><node package="com.tacobell.ordering" text="Free Welcome Reward"/></hierarchy>')
        self.assertEqual(self.call_verify([screen(),screen('001234'),signed])['stage'],'signed_in')
        self.tap.assert_called_once_with('adb','device',text='VERIFY')
        self.assertTrue(any(c.args[0][-2:]==['text','001234'] for c in self.run.call_args_list))
    def test_wrong_app_never_gets_code(self):
        with self.assertRaises(ValueError): self.call_verify([screen(valid=False)])
        self.run.assert_not_called()
    def test_failed_entry_never_submits(self):
        with self.assertRaises(ValueError): self.call_verify([screen(),screen('')])
        self.tap.assert_not_called()
    def test_rejected_code_stops(self):
        error='<node package="com.tacobell.ordering" text="Invalid code"/>'
        with self.assertRaisesRegex(ValueError,'did not accept'): self.call_verify([screen(),screen('001234'),screen(extra=error)])
    def test_unknown_screen_does_not_claim_success(self):
        result=self.call_verify([screen(),screen('001234')]+[ET.Element('hierarchy')]*6)
        self.assertEqual(result['stage'],'verification_unconfirmed')
