import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from links import extract_links
from settings import load_settings, save_settings


class SettingsFilterTests(unittest.TestCase):
    def test_filter_only_cas(self):
        cas = [f'https://t.me/combot/cas?startapp={i}' for i in range(13)]
        keep = ['https://t.me/combot', 'https://t.me/other/cas?startapp=1',
                'https://example.com/combot/cas', 'https://t.me/combot/casino']
        msg = SimpleNamespace(message=' '.join(cas + keep), entities=[])
        self.assertEqual(extract_links(msg, exclude_cas=True), keep)
        self.assertEqual(len(extract_links(msg)), 17)

    def test_button_cas(self):
        msg = SimpleNamespace(message='', entities=[], reply_markup=SimpleNamespace(rows=[
            SimpleNamespace(buttons=[SimpleNamespace(url='https://t.me/combot/cas?startapp=9')])]))
        self.assertEqual(extract_links(msg, exclude_cas=True), [])

    def test_remember_and_forget(self):
        with tempfile.TemporaryDirectory() as folder, patch('settings.session_directory', return_value=Path(folder)):
            save_settings('12345', 'abc', True, True)
            self.assertEqual(load_settings()['api_hash'], 'abc')
            save_settings('12345', 'abc', False, False)
            self.assertNotIn('api_hash', load_settings())
            self.assertNotIn('api_id', load_settings())
            (Path(folder) / 'settings.json').write_text('{broken')
            self.assertEqual(load_settings(), {})
