@echo off
title SuperOllama - AI Studio & Client
cd /d "%~dp0"

echo =========================================================
echo             Starting SuperOllama Client
echo =========================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your PATH!
    echo Please install Python 3.10+ from python.org and add to PATH.
    pause
    exit /b 1
)

:: Ensure dependencies are present
echo [1/2] Verifying dependencies...
python -c "import fastapi, uvicorn, httpx, ddgs, libzim" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing missing requirements...
    pip install -r requirements.txt
)

echo [2/2] Launching SuperOllama Server...
echo.
echo Desktop Web UI: http://localhost:8000
echo Access from Phone/Tablet: Use your PC local IP on port 8000 (e.g. http://192.168.x.x:8000)
echo.

:: Automatically open default browser after 2 seconds
start "" http://localhost:8000

:: Start server
python main.py

pause
