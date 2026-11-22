@echo off
setlocal
cd /d "%~dp0backend"
echo ========================================
echo MediMemory - Backend setup
echo ========================================
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher 'py' was not found. Install Python 3.10+ and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv (
  echo Creating Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERROR: Could not create virtual environment.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo ERROR: Could not activate the virtual environment.
  pause
  exit /b 1
)
echo Installing backend dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: pip upgrade failed. Check internet access and Python installation.
  pause
  exit /b 1
)
pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Backend dependencies failed to install. Read the error above.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
echo.
echo Starting backend at http://127.0.0.1:8000
echo API documentation: http://127.0.0.1:8000/docs
echo Keep this window open while using MediMemory.
python -m uvicorn app.main:app --reload
if errorlevel 1 echo ERROR: Backend stopped. Read the error above.
pause
