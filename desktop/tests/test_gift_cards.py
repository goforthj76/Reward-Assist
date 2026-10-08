import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gift_cards import apply_gift_card, validate_gift_card


def form(number="", pin=""):
    root = ET.Element("hierarchy")
    for text in ("Taco Bell Gift Card Number *", "PIN (3 or 8 digit code) *"):
        ET.SubElement(root, "node", {"text": text, "package": "com.tacobell.ordering"})
    for text in (number, pin):
        ET.SubElement(root, "node", {"text": text, "class": "android.widget.EditText",
                                     "resource-id": "input_field", "bounds": "[0,0][100,100]"})
    return root


class GiftCardTests(unittest.TestCase):
    def test_validation_preserves_leading_zeroes(self):
        self.assertEqual(validate_gift_card({"number": "0000-1234 5678", "pin": "001"}),
                         {"number": "000012345678", "pin": "001"})
        self.assertIsNone(validate_gift_card(None))
        for value in ({"number": "12;ls", "pin": "123"}, {"number": "123", "pin": "12"},
                      {"number": "", "pin": "123"}, "123"):
            with self.assertRaises(ValueError):
                validate_gift_card(value)

    @patch("gift_cards.time.sleep")
    @patch("gift_cards.subprocess.run")
    def test_only_add_card_is_submitted(self, run, sleep):
        after = ET.fromstring('<hierarchy><node package="com.tacobell.ordering" text="Select Payment Method"/></hierarchy>')
        read = Mock(side_effect=[form(), form(), form(), form("0000 1234", "001"), after])
        tap = Mock(return_value=True)
        result = apply_gift_card("adb", "device", {"number": "00001234", "pin": "001"}, read, tap, lambda b: (50, 50))
        tap.assert_called_once_with("adb", "device", text="ADD GIFT CARD")
        self.assertIn("Verify", result)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(any(command[-1] == "001" for command in commands))
        self.assertTrue(any(command.count("KEYCODE_DEL") == 64 for command in commands))

    @patch("gift_cards.subprocess.run")
    def test_unverified_entry_never_submits(self, run):
        tap = Mock()
        with self.assertRaisesRegex(ValueError, "could not be verified"):
            apply_gift_card("adb", "device", {"number": "1234", "pin": "123"},
                            Mock(return_value=form()), tap, lambda b: (50, 50))
        tap.assert_not_called()

    def test_wrong_app_never_receives_card(self):
        tap = Mock()
        with self.assertRaisesRegex(ValueError, "Open Taco Bell"):
            apply_gift_card("adb", "device", {"number": "1234", "pin": "123"},
                            Mock(return_value=ET.Element("hierarchy")), tap, lambda b: (50, 50))
        tap.assert_not_called()

    @patch("gift_cards.time.sleep")
    @patch("gift_cards.subprocess.run")
    def test_rejected_card_does_not_report_success(self, run, sleep):
        with self.assertRaisesRegex(ValueError, "has not confirmed"):
            apply_gift_card("adb", "device", {"number": "1234", "pin": "123"},
                            Mock(return_value=form("1234", "123")), Mock(return_value=True), lambda b: (50, 50))


if __name__ == "__main__":
    unittest.main()
