@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo        DHRUVA CARE - LOCAL LAUNCHER
echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating Python virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Python 3 was not found. Install Python 3.10-3.13 and try again.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment already exists.
)

echo [2/3] Installing/updating dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo [3/3] Starting Dhruva Care...
echo.
echo Open http://127.0.0.1:5050/ in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.
.venv\Scripts\python.exe app.py
pause
