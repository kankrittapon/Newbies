@echo off
echo Deploying NewbiesBot...

REM Check if exe exists
if not exist "NewbiesBot.exe" (
    echo ERROR: NewbiesBot.exe not found
    echo Run build\build_simple.bat first
    pause
    exit /b 1
)

REM Create release folder
set RELEASE_DIR=release_%date:~-4,4%%date:~-10,2%%date:~-7,2%
mkdir "%RELEASE_DIR%" 2>nul

REM Copy files
echo Copying files to %RELEASE_DIR%...
copy "NewbiesBot.exe" "%RELEASE_DIR%\"

REM Copy documentation (if exists)
if exist "README.md" copy "README.md" "%RELEASE_DIR%\"
if exist "USER_MANUAL.md" copy "USER_MANUAL.md" "%RELEASE_DIR%\"
if exist "SETUP_GUIDE.md" copy "SETUP_GUIDE.md" "%RELEASE_DIR%\"
if exist "TROUBLESHOOTING.md" copy "TROUBLESHOOTING.md" "%RELEASE_DIR%\"

REM Copy assets folder (if exists)
if exist "assets" (
    xcopy "assets" "%RELEASE_DIR%\assets\" /E /I /Q
) else (
    echo WARNING: assets folder not found
)

echo SUCCESS: Release package created in %RELEASE_DIR%
echo Ready for distribution!

pause