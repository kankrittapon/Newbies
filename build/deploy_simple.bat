@echo off
echo Simple Deploy - NewbiesBot

REM Check if exe exists
if not exist "C:\Newbies\NewbiesBot.exe" (
    echo ERROR: NewbiesBot.exe not found at C:\Newbies\
    pause
    exit /b 1
)

REM Create simple release folder
set RELEASE_DIR=NewbiesBot_Release
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

REM Copy essential files only
echo Copying NewbiesBot.exe...
copy "C:\Newbies\NewbiesBot.exe" "%RELEASE_DIR%\"

REM Create simple readme
echo Creating README.txt...
echo NewbiesBot - Ready to Use > "%RELEASE_DIR%\README.txt"
echo. >> "%RELEASE_DIR%\README.txt"
echo Double-click NewbiesBot.exe to run >> "%RELEASE_DIR%\README.txt"
echo No installation required >> "%RELEASE_DIR%\README.txt"

echo SUCCESS: Simple release created in %RELEASE_DIR%
echo Contents:
dir "%RELEASE_DIR%"

pause