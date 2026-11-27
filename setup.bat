@echo off
setlocal EnableExtensions EnableDelayedExpansion
title MediMemory - setup
cd /d "%~dp0"

echo.
echo ============================================================
echo   MediMemory setup (Windows)
echo ============================================================
echo.

rem ---------- Python (prefer a supported version: 3.12, 3.13, 3.11, 3.10) ----------
set "PY="
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined PY (
    py -%%V --version >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  python --version >nul 2>&1 && (
    for /f "delims=" %%v in ('python --version 2^>^&1') do echo [ERROR] Found %%v, but MediMemory needs Python 3.10 - 3.13.
    echo         Install Python 3.12 ^(Windows installer^) from https://www.python.org/downloads/windows/
    echo         ^(you can keep your current Python; setup will find 3.12 automatically^)
    goto :fail
  )
)
if not defined PY (
  echo [ERROR] Python was not found.
  echo         Install Python 3.10 - 3.13 from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during installation.
  goto :fail
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo [OK] %%v found
%PY% -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 (
  echo [ERROR] MediMemory needs Python 3.10, 3.11, 3.12 or 3.13.
  goto :fail
)

rem ---------- Node.js ----------
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js was not found. Install the LTS version from https://nodejs.org/
  goto :fail
)
for /f "delims=" %%v in ('node --version') do echo [OK] Node.js %%v found
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm was not found. Reinstall Node.js from https://nodejs.org/
  goto :fail
)

rem ---------- .env ----------
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo [OK] Created .env from .env.example  ^(add your API keys there^)
) else (
  echo [OK] .env already exists
)

rem ---------- encryption key (created once, never change it later) ----------
%PY% -c "import re,secrets,pathlib; p=pathlib.Path('.env'); t=p.read_text(encoding='utf-8'); m=re.search(r'^DATA_ENCRYPTION_KEY=(.*)$', t, re.M); (p.write_text(re.sub(r'^DATA_ENCRYPTION_KEY=.*$', 'DATA_ENCRYPTION_KEY='+secrets.token_urlsafe(32), t, flags=re.M) if not m.group(1).strip() else t, encoding='utf-8') if m else p.write_text(t.rstrip()+'\nDATA_ENCRYPTION_KEY='+secrets.token_urlsafe(32)+'\n', encoding='utf-8'))"
if errorlevel 1 (
  echo [WARN] Could not create DATA_ENCRYPTION_KEY automatically. Add any long random value to .env yourself.
) else (
  echo [OK] Encryption key is set in .env  ^(keep it; changing it makes saved data unreadable^)
)

rem ---------- Backend ----------
echo.
echo --- Backend: creating virtual environment and installing packages ---
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Could not create the Python virtual environment.
    goto :fail
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :pipfail
python -m pip install -r requirements.txt
if errorlevel 1 goto :pipfail

echo.
echo --- Backend: creating database tables ---
python -m alembic upgrade head
if errorlevel 1 (
  echo [ERROR] Database migration failed. Check DATABASE_URL in .env
  goto :fail
)

echo.
echo --- Backend: loading fictional demo data ---
python -m app.seed
if errorlevel 1 (
  echo [ERROR] Loading demo data failed.
  goto :fail
)
call deactivate >nul 2>&1

rem ---------- Frontend ----------
echo.
echo --- Frontend: installing packages (this can take a few minutes) ---
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
  echo [ERROR] npm install failed. Check your internet connection and try again.
  goto :fail
)

cd /d "%~dp0"
echo.
echo ============================================================
echo   Setup complete!
echo   1. Open .env and add ELEVENLABS_API_KEY and LLM_API_KEY ^(Gemini key from aistudio.google.com^)
echo      Gemini: LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai and LLM_MODEL=^<Flash model name^>
echo      Optional OCR on Windows: install Tesseract ^(UB Mannheim build^) with Tamil and Hindi, then set
echo      TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe in .env. Without it, photos are read by Gemini.
echo   2. Double-click start_backend.bat   ^(keep that window open^)
echo   3. Double-click start_frontend.bat  ^(keep that window open^)
echo   4. Open http://localhost:5173
echo   Demo login: demo@medimemory.app / Demo@1234
echo ============================================================
echo.
pause
exit /b 0

:pipfail
echo [ERROR] Installing Python packages failed. Check your internet connection.
echo         If a package fails to build, make sure you are using Python 3.10 - 3.13.
:fail
echo.
echo Setup did not finish. Read the message above, fix the problem and run setup.bat again.
pause
exit /b 1
