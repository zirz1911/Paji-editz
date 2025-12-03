@echo off
cd /d "%~dp0"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Please run setup first.
    pause
    exit /b
)

python main.py
pause
