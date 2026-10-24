@echo off
title Royal Ludo Championship
echo ===================================================
echo   Starting Royal Ludo with Real-Time Audio Calling
echo ===================================================
echo Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not found in your PATH!
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo Installing / Verifying requirements...
python -m pip install -r requirements.txt --quiet

echo Launching game server...
python main.py
pause
