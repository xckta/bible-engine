@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo.
  echo Could not open the Bible Only Engine folder.
  echo Move the unzipped folder somewhere simple, then try again.
  pause
  exit /b 1
)

title Bible Only Engine

echo.
echo ========================================
echo        BIBLE ONLY ENGINE
echo ========================================
echo.

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"

if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo Python is not installed.
  echo Install Python 3.11 or newer, then double-click this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up the app...
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)

echo Installing/updating the app...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -q -e .
if errorlevel 1 goto :fail

if not exist "data\bible.db" (
  echo Loading the included Bible demo corpus...
  ".venv\Scripts\python.exe" "scripts\seed_demo.py"
  if errorlevel 1 goto :fail
)

echo.
echo Starting Bible Only Engine...
echo Your browser will open automatically.
echo Keep this window open while you use the app.
echo Press Ctrl+C here when you want to stop it.
echo.

start "" ".venv\Scripts\pythonw.exe" "scripts\open_browser.py"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

exit /b 0

:fail
echo.
echo Setup failed. Copy the error above into ChatGPT.
pause
exit /b 1
