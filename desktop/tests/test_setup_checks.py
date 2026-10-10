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

    def test_install_copies_extension_and_provides_zip(self):
        import tempfile
        import zipfile
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            base=Path(folder)
            source=base/'payload';source.mkdir()
            (source/'Rewards Assistant.exe').write_bytes(b'test exe')
            helper=source/'chrome_extension';helper.mkdir()
            (helper/'manifest.json').write_text('{"manifest_version":3}')
            (helper/'background.js').write_text('// test')
            target=base/'install'
            for name,value in [('INSTALL_ROOT',target),('APP_EXE',target/'Reward Assist.exe'),('EXTENSION_ROOT',target/'browser-helper')]:
                stack.enter_context(patch.object(setup_app,name,value))
            stack.enter_context(patch.object(setup_app,'bundled',side_effect=lambda name:source/name))
            stack.enter_context(patch.object(setup_app,'find_adb',return_value=Path('adb')))
            stack.enter_context(patch.object(setup_app,'find_chrome',return_value=Path('chrome')))
            stack.enter_context(patch.object(setup_app,'make_shortcut'))
            error=stack.enter_context(patch.object(setup_app.messagebox,'showerror'))
            app=setup_app.SetupWindow();app.root.withdraw();app.desktop.set(False)
            try:
                app.finish_install()
                error.assert_not_called()
                self.assertEqual((target/'browser-helper/background.js').read_text(),'// test')
                with zipfile.ZipFile(target/'Reward-Assist-Chrome-Extension.zip') as bundle:
                    self.assertIn('browser-helper/manifest.json',bundle.namelist())
                self.assertEqual(app.guide_step,0)
            finally: app.root.destroy()
