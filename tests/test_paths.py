import unittest
from pathlib import Path
from unittest.mock import patch
from app_paths import export_directory, session_directory


class PathTests(unittest.TestCase):
    def test_mac_paths_outside_bundle(self):
        with patch('app_paths.sys.platform', 'darwin'):
            self.assertEqual(export_directory(), Path.home() / 'Downloads' / 'TelegramLinks')
            self.assertEqual(session_directory(), Path.home() / 'Library' / 'Application Support' / 'TelegramLinkExporter')

    def test_windows_export_location(self):
        with patch('app_paths.sys.platform', 'win32'):
            self.assertEqual(export_directory(), Path(__file__).resolve().parents[1] / 'exports')
