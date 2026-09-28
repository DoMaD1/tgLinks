"""Local preferences, separate from source files and distributable builds."""
import json
import os
import tempfile
from app_paths import session_directory


def load_settings():
    try:
        value = json.loads((session_directory() / 'settings.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(api_id, api_hash, remember, exclude_cas):
    folder = session_directory()
    folder.mkdir(parents=True, exist_ok=True)
    data = {'remember': bool(remember), 'exclude_cas': bool(exclude_cas)}
    if remember:
        data.update(api_id=api_id.strip(), api_hash=api_hash.strip())
    fd, name = tempfile.mkstemp(dir=folder, prefix='settings-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(data, file)
        os.replace(name, folder / 'settings.json')
    finally:
        if os.path.exists(name):
            os.unlink(name)
