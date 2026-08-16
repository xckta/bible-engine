@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo.
  echo Could not open the Bible Engine folder.
  pause
  exit /b 1
)

title Bible Engine

echo.
echo ========================================
echo             BIBLE ENGINE
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
  echo Python 3.11 or newer is required.
  echo Install Python, then double-click this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up Bible Engine...
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)

".venv\Scripts\python.exe" -m pip install -q --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -q -e .
if errorlevel 1 goto :fail

where codex >nul 2>nul
if errorlevel 1 (
  echo Codex CLI is not installed. Installing it now...
  where npm >nul 2>nul
  if errorlevel 1 (
    echo.
    echo Codex CLI is required and npm was not found.
    echo Install Node.js, then run this file again.
    goto :fail
  )
  call npm install -g @openai/codex@latest
  if errorlevel 1 goto :fail
  where codex >nul 2>nul
  if errorlevel 1 (
    echo Codex installed, but Windows cannot find it on PATH yet.
    echo Close this window and double-click START_BIBLE_ENGINE.bat again.
    pause
    exit /b 1
  )
)

set "AUTH_FILE=%TEMP%\bible-engine-codex-auth-%RANDOM%.txt"
codex login status > "%AUTH_FILE%" 2>&1
set "AUTH_RC=%ERRORLEVEL%"
if "%AUTH_RC%"=="0" (
  findstr /i "ChatGPT" "%AUTH_FILE%" >nul 2>nul
  if not errorlevel 1 goto :auth_ok
)

echo.
echo Bible Engine uses your ChatGPT Codex login.
echo The official Codex sign-in will open now.
echo.
codex login
if errorlevel 1 (
  del "%AUTH_FILE%" >nul 2>nul
  goto :fail
)
codex login status > "%AUTH_FILE%" 2>&1
if errorlevel 1 (
  del "%AUTH_FILE%" >nul 2>nul
  goto :fail
)
findstr /i "ChatGPT" "%AUTH_FILE%" >nul 2>nul
if errorlevel 1 (
  echo.
  echo Codex is authenticated, but not with ChatGPT.
  echo Bible Engine is intentionally configured not to use API-key auth.
  del "%AUTH_FILE%" >nul 2>nul
  goto :fail
)

:auth_ok
del "%AUTH_FILE%" >nul 2>nul

echo Checking Bible corpus...
".venv\Scripts\python.exe" "scripts\check_corpus.py" >nul 2>nul
if errorlevel 1 (
  echo First run: downloading the complete WEB and ASV Bibles...
  ".venv\Scripts\python.exe" "scripts\fetch_public_domain.py"
  if errorlevel 1 goto :fail
  echo Loading the complete Bible corpus...
  ".venv\Scripts\python.exe" "scripts\seed_public_domain.py"
  if errorlevel 1 goto :fail
  ".venv\Scripts\python.exe" "scripts\check_corpus.py"
  if errorlevel 1 goto :fail
)

echo.
echo Codex: ChatGPT authenticated
echo Model: gpt-5.6-luna
echo Reasoning: medium
echo Corpus: full WEB + ASV
echo.
echo Starting Bible Engine...
echo Keep this window open while you use the app.
echo Press Ctrl+C here when you want to stop it.
echo.

start "" ".venv\Scripts\pythonw.exe" "scripts\open_browser.py"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
exit /b 0

:fail
echo.
echo Bible Engine setup failed. Copy the error above into ChatGPT.
pause
exit /b 1
