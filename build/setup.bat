@echo off
chcp 65001 >nul
echo Setting up Python 3.12 build environment...

REM Check Python 3.12
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.12 not found
    echo Please install Python 3.12 from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo SUCCESS: Python 3.12 found

REM Install dependencies
echo Installing build dependencies...
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r build\requirements.txt

echo SUCCESS: Setup complete!
echo Run 'build\build.bat' to build the executable
pause