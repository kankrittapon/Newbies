@echo off
echo Build with Icon - NewbiesBot

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

REM Try different icon files
echo Trying robot_clean.ico...
py -3.12 -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter --windows-icon-from-ico=assets/robot_clean.ico gui_app.py --output-filename=NewbiesBot.exe

if not exist "NewbiesBot.exe" (
    echo Trying bokchoy_robot.ico...
    py -3.12 -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter --windows-icon-from-ico=assets/bokchoy_robot.ico gui_app.py --output-filename=NewbiesBot.exe
)

if not exist "NewbiesBot.exe" (
    echo Building without icon...
    py -3.12 -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter gui_app.py --output-filename=NewbiesBot.exe
)

if exist "NewbiesBot.exe" (
    echo SUCCESS: NewbiesBot.exe created
) else (
    echo ERROR: Build failed
)

pause