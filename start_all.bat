@echo off
setlocal
start "MediMemory Backend" /D "%~dp0" cmd /k "call start_backend.bat"
start "MediMemory Frontend" /D "%~dp0" cmd /k "call start_frontend.bat"
echo.
echo MediMemory startup windows opened.
echo Wait for both setup processes, then visit http://localhost:5173
 echo Keep both windows open while using MediMemory.
pause
