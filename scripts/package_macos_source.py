"""Package an explicit allowlist; never include sessions or collected data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = ['app.py', 'app_paths.py', 'links.py', 'scanner.py', 'requirements.txt',
         'build_macos.sh', 'MACOS.md', '.gitignore', '.github/workflows/macos.yml',
         'scripts/verify_macos.py', 'tests/test_links.py', 'tests/test_scanner.py',
         'tests/test_paths.py']
target = root / 'dist' / 'TelegramLinks-macOS-source.zip'
target.parent.mkdir(exist_ok=True)
with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
    for name in files:
        archive.writestr(name, (root / name).read_text(encoding='utf-8').replace('\r\n', '\n'))
with ZipFile(target) as archive:
    assert archive.testzip() is None
    assert sorted(archive.namelist()) == sorted(files)
print(target)
