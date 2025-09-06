@echo off
echo Minimal Build - NewbiesBot

REM Check Python 3.12
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.12 not found
    pause
    exit /b 1
)

REM Go to project root
cd /d "%~dp0\.."

REM Install Nuitka
py -3.12 -m pip install nuitka

REM Clean
if exist "NewbiesBot.exe" del "NewbiesBot.exe"

REM Build (minimal options)
py -3.12 -m nuitka --onefile --enable-plugin=tk-inter gui_app.py

if exist "gui_app.exe" (
    ren "gui_app.exe" "NewbiesBot.exe"
    echo SUCCESS: NewbiesBot.exe created
) else (
    echo ERROR: Build failed
)

pause