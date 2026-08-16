@echo off
if not defined BIBLE_ENGINE_KEEP_OPEN (
  set "BIBLE_ENGINE_KEEP_OPEN=1"
  cmd.exe /k call "%~f0"
  exit /b
)

setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 goto :folder_fail

set "LOG=%~dp0bible-engine-startup.log"
> "%LOG%" echo Bible Engine startup log
>> "%LOG%" echo Started: %DATE% %TIME%
>> "%LOG%" echo Folder: %CD%

title Bible Engine

echo.
echo ========================================
echo             BIBLE ENGINE
echo ========================================
echo.
echo Startup log: bible-engine-startup.log
echo.

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if defined PY goto :python_found
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto :python_found

echo Python 3.11 or newer is required.
>> "%LOG%" echo ERROR: Python was not found on PATH.
goto :fail

:python_found
%PY% --version >> "%LOG%" 2>&1

if exist ".venv\Scripts\python.exe" goto :venv_ready
echo First run: setting up Bible Engine...
>> "%LOG%" echo Creating virtual environment...
%PY% -m venv .venv >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

:venv_ready
echo Checking Python environment...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip >> "%LOG%" 2>&1
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -q -e . >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo Checking Codex...
where codex >> "%LOG%" 2>&1
if not errorlevel 1 goto :codex_present

echo Codex CLI is not installed. Installing it now...
where npm >> "%LOG%" 2>&1
if errorlevel 1 goto :npm_missing
call npm install -g @openai/codex@latest >> "%LOG%" 2>&1
if errorlevel 1 goto :fail
where codex >> "%LOG%" 2>&1
if errorlevel 1 goto :codex_path_fail

:codex_present
codex --version >> "%LOG%" 2>&1
set "AUTH_FILE=%TEMP%\bible-engine-codex-auth-%RANDOM%.txt"
codex login status > "%AUTH_FILE%" 2>&1
set "AUTH_RC=%ERRORLEVEL%"
type "%AUTH_FILE%" >> "%LOG%" 2>&1
if not "%AUTH_RC%"=="0" goto :codex_login
findstr /i "ChatGPT" "%AUTH_FILE%" >nul 2>nul
if errorlevel 1 goto :codex_login
goto :auth_ok

:codex_login
echo.
echo Bible Engine needs the official Codex ChatGPT sign-in.
echo A browser sign-in may open now.
echo.
>> "%LOG%" echo Starting codex login...
codex login
if errorlevel 1 goto :auth_fail
codex login status > "%AUTH_FILE%" 2>&1
set "AUTH_RC=%ERRORLEVEL%"
type "%AUTH_FILE%" >> "%LOG%" 2>&1
if not "%AUTH_RC%"=="0" goto :auth_fail
findstr /i "ChatGPT" "%AUTH_FILE%" >nul 2>nul
if errorlevel 1 goto :wrong_auth

:auth_ok
del "%AUTH_FILE%" >nul 2>nul

echo Checking Bible corpus...
".venv\Scripts\python.exe" "scripts\check_corpus.py" >> "%LOG%" 2>&1
if not errorlevel 1 goto :corpus_ready

echo First run: downloading the complete WEB and ASV Bibles...
".venv\Scripts\python.exe" "scripts\fetch_public_domain.py" >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo Loading the complete Bible corpus...
".venv\Scripts\python.exe" "scripts\seed_public_domain.py" >> "%LOG%" 2>&1
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" "scripts\check_corpus.py" >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

:corpus_ready
echo Checking application startup...
".venv\Scripts\python.exe" -c "import app.main; print('Application import OK')" >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

powershell -NoProfile -Command "$p=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if($p){exit 1}else{exit 0}" >> "%LOG%" 2>&1
if errorlevel 1 goto :port_busy

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
>> "%LOG%" echo Starting Uvicorn on http://127.0.0.1:8000

start "" ".venv\Scripts\pythonw.exe" "scripts\open_browser.py"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
set "SERVER_RC=%ERRORLEVEL%"
>> "%LOG%" echo Uvicorn exited with code %SERVER_RC% at %DATE% %TIME%

echo.
if "%SERVER_RC%"=="0" (
  echo Bible Engine stopped.
) else (
  echo Bible Engine server stopped unexpectedly with exit code %SERVER_RC%.
  echo The startup log will open in Notepad.
  start "" notepad.exe "%LOG%"
)
echo.
echo Press any key to close this window.
pause >nul
exit /b %SERVER_RC%

:npm_missing
echo Node.js/npm was not found, so Codex CLI could not be installed.
>> "%LOG%" echo ERROR: npm not found.
goto :fail

:codex_path_fail
echo Codex installed, but Windows cannot find it on PATH yet.
echo Close this window, reopen it, and run START_BIBLE_ENGINE.bat again.
>> "%LOG%" echo ERROR: Codex installed but was not found on PATH.
goto :fail

:auth_fail
echo Codex ChatGPT sign-in did not complete successfully.
>> "%LOG%" echo ERROR: Codex login failed.
goto :fail

:wrong_auth
echo Codex is authenticated, but Bible Engine could not verify ChatGPT authentication.
echo Run: codex logout
echo Then run this launcher again and choose ChatGPT sign-in.
>> "%LOG%" echo ERROR: Codex authentication did not report ChatGPT.
goto :fail

:port_busy
echo Port 8000 is already being used by another program.
echo Close the older Bible Engine/server window and run this launcher again.
>> "%LOG%" echo ERROR: TCP port 8000 is already listening.
goto :fail

:folder_fail
echo Could not open the Bible Engine folder.
pause
exit /b 1

:fail
echo.
echo ========================================
echo          BIBLE ENGINE FAILED
echo ========================================
echo.
echo The error details are saved here:
echo %LOG%
echo.
echo Opening the log in Notepad now.
start "" notepad.exe "%LOG%"
echo Press any key to close this window.
pause >nul
exit /b 1
