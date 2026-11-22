@echo off
setlocal
cd /d "%~dp0frontend"
echo ========================================
echo MediMemory - Frontend setup
echo ========================================
where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js was not found. Install Node.js, then reopen this file.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: npm was not found. Reinstall Node.js with npm included.
  pause
  exit /b 1
)
echo Node and npm versions:
call node --version
call npm --version
if not exist node_modules (
  echo.
  echo Installing frontend dependencies. This requires internet access...
  call npm install
  if errorlevel 1 (
    echo ERROR: Frontend dependencies failed to install. Read the error above.
    pause
    exit /b 1
  )
)
if not exist .env copy .env.example .env >nul
echo.
echo Starting frontend at http://localhost:5173
echo Keep this window open while using MediMemory.
call npm run dev
if errorlevel 1 echo ERROR: Frontend stopped. Read the error above.
pause
