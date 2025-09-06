@echo off
chcp 65001 >nul
echo Building NewbiesBot with Python 3.12...

REM Check Python 3.12
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.12 not found
    echo Please install Python 3.12 first
    pause
    exit /b 1
)

REM Go to root directory
cd /d "%~dp0\.."

REM Create build config
echo Creating build config...
py -3.12 build\build_config.py
if errorlevel 1 (
    echo ERROR: Build config failed
    pause
    exit /b 1
)

REM Install Nuitka
echo Installing Nuitka...
py -3.12 -m pip install nuitka

REM Clean old files
if exist "NewbiesBot.exe" del "NewbiesBot.exe"
if exist "NewbiesBot.dist" rmdir /s /q "NewbiesBot.dist"
if exist "NewbiesBot.build" rmdir /s /q "NewbiesBot.build"

REM Build with Nuitka
echo Building executable...
py -3.12 -m nuitka --onefile --windows-console-mode=disable --windows-icon-from-ico=assets/robot.ico --include-data-dir=assets=assets --include-module=tkinter --include-module=requests --include-module=playwright --include-module=selenium --include-package=webdriver_manager --output-filename=NewbiesBot.exe gui_app.py

if exist "NewbiesBot.exe" (
    echo SUCCESS: Build completed!
    echo File: NewbiesBot.exe
) else (
    echo ERROR: Build failed
    pause
    exit /b 1
)

pause