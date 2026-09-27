@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto build
py -3 -m venv .venv
if errorlevel 1 goto failed
:build
.venv\Scripts\python.exe -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --workpath build\windows --name TelegramLinks app.py
if errorlevel 1 goto failed
echo Built: dist\TelegramLinks.exe
pause
exit /b 0
:failed
echo Build failed. See the error above.
pause
exit /b 1
