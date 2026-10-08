import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import Mock, patch
import setup_checks
import setup_app

class SetupTests(unittest.TestCase):
    def test_authorized_device_app_inventory(self):
        results=[Mock(returncode=0,stdout=''),Mock(returncode=0,stdout='List of devices attached\nabc\tdevice\n'),Mock(returncode=0,stdout='package:com.tacobell.ordering\n')]
        with patch.object(setup_checks.subprocess,'run',side_effect=results):
            report=setup_checks.inspect_android('adb')
        self.assertIn('Taco Bell: installed',report)
        self.assertIn('Dutch Bros: install from Google Play',report)
    def test_unauthorized_device_explains_prompt(self):
        results=[Mock(returncode=0,stdout=''),Mock(returncode=0,stdout='abc\tunauthorized\n')]
        with patch.object(setup_checks.subprocess,'run',side_effect=results):
            self.assertIn('allow USB debugging',setup_checks.inspect_android('adb'))
    def test_guide_pages_construct_before_launch(self):
        app=setup_app.SetupWindow()
        app.root.withdraw()
        try:
            app.show_setup_guide()
            for step in range(3):
                app.guide_step=step
                app.draw_guide()
                app.root.update_idletasks()
                self.assertGreater(len(app.guide_frame.winfo_children()),3)
        finally:
            app.root.destroy()
