"""Run the bundled executable, not the source interpreter, with a timeout."""
import json
from pathlib import Path
import subprocess
import tempfile

binary = Path('dist/macos/TelegramLinks.app/Contents/MacOS/TelegramLinks').resolve()
with tempfile.TemporaryDirectory() as directory:
    report = Path(directory) / 'report.json'
    subprocess.run([str(binary), '--smoke-test', str(report)], check=True, timeout=60)
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result == {'status': 'ok', 'platform': 'darwin', 'frozen': True}, result
    print('PASS: packaged macOS application, Tcl/Tk window and HTML export')
