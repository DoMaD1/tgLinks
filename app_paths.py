"""Writable locations outside the macOS application bundle."""
import os
import sys
from pathlib import Path


def export_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Downloads' / 'TelegramLinks'
    base = Path(sys.executable) if getattr(sys, 'frozen', False) else Path(__file__)
    return base.resolve().parent / 'exports'


def session_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'TelegramLinkExporter'
    return Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'TelegramLinkExporter'
