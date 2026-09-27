#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin ]]; then
  echo "This build must run on macOS (a Mac or GitHub Actions macOS runner)."
  exit 1
fi
python3 -m venv .venv-macos
PY="$PWD/.venv-macos/bin/python"
"$PY" -m pip install -r requirements.txt 'pyinstaller>=6.22.3,<7'
"$PY" -c 'import tkinter; root = tkinter.Tk(); root.withdraw(); root.update(); root.destroy()'
"$PY" -m unittest discover -s tests -v
"$PY" -m PyInstaller --noconfirm --windowed --onedir --name TelegramLinks \
  --osx-bundle-identifier org.telegramlinks.desktop \
  --workpath build/macos --distpath dist/macos app.py
"$PY" scripts/verify_macos.py
ARCH="$(uname -m)"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent dist/macos/TelegramLinks.app "dist/TelegramLinks-macOS-${ARCH}.zip"
echo "Built and smoke-tested: dist/TelegramLinks-macOS-${ARCH}.zip"
