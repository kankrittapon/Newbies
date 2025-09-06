@echo off
chcp 65001 >nul
echo Simple Build Script for NewbiesBot

REM Check Python 3.12
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.12 not found
    pause
    exit /b 1
)

echo SUCCESS: Python 3.12 found

REM Go to project root
cd /d "%~dp0\.."

REM Install Nuitka
echo Installing Nuitka...
py -3.12 -m pip install nuitka

REM Clean
echo Cleaning old files...
if exist "NewbiesBot.exe" del "NewbiesBot.exe"
if exist "NewbiesBot.dist" rmdir /s /q "NewbiesBot.dist" 2>nul
if exist "NewbiesBot.build" rmdir /s /q "NewbiesBot.build" 2>nul

REM Build
echo Building executable...
py -3.12 -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter gui_app.py --output-filename=NewbiesBot.exe

if exist "NewbiesBot.exe" (
    echo SUCCESS: NewbiesBot.exe created
) else (
    echo ERROR: Build failed
)

pause