@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto run
py -3 -m venv .venv
if errorlevel 1 goto failed
:run
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Install Python 3.10+ with Tcl/Tk and Python Launcher, then try again.
pause
