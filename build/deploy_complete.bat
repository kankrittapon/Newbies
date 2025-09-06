@echo off
echo Complete Deploy - NewbiesBot

REM Check if exe exists
if not exist "C:\Newbies\NewbiesBot.exe" (
    echo ERROR: NewbiesBot.exe not found at C:\Newbies\
    echo Run build\build_simple.bat first
    pause
    exit /b 1
)

REM Create release folder with timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "RELEASE_DIR=NewbiesBot_v1.0.0_%YYYY%%MM%%DD%"

if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

echo Creating release package: %RELEASE_DIR%

REM Copy main executable
echo [1/6] Copying NewbiesBot.exe...
copy "C:\Newbies\NewbiesBot.exe" "%RELEASE_DIR%\" >nul

REM Copy documentation
echo [2/6] Copying documentation...
copy "README.md" "%RELEASE_DIR%\" >nul
copy "USER_MANUAL.md" "%RELEASE_DIR%\" >nul
copy "SETUP_GUIDE.md" "%RELEASE_DIR%\" >nul
copy "TROUBLESHOOTING.md" "%RELEASE_DIR%\" >nul

REM Copy assets
echo [3/6] Copying assets...
xcopy "assets" "%RELEASE_DIR%\assets\" /E /I /Q >nul

REM Copy version info
echo [4/6] Copying version info...
if exist "version.py" copy "version.py" "%RELEASE_DIR%\" >nul

REM Create launcher script
echo [5/6] Creating launcher...
echo @echo off > "%RELEASE_DIR%\Start_NewbiesBot.bat"
echo echo Starting NewbiesBot... >> "%RELEASE_DIR%\Start_NewbiesBot.bat"
echo NewbiesBot.exe >> "%RELEASE_DIR%\Start_NewbiesBot.bat"

REM Create release info
echo [6/6] Creating release info...
echo NewbiesBot Release Package > "%RELEASE_DIR%\RELEASE_INFO.txt"
echo Version: 1.0.0 >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo Build Date: %DD%/%MM%/%YYYY% >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo. >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo Files included: >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo - NewbiesBot.exe (Main application) >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo - Start_NewbiesBot.bat (Launcher) >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo - Documentation files >> "%RELEASE_DIR%\RELEASE_INFO.txt"
echo - Assets folder >> "%RELEASE_DIR%\RELEASE_INFO.txt"

echo.
echo SUCCESS: Release package created!
echo Folder: %RELEASE_DIR%
echo.
echo Contents:
dir "%RELEASE_DIR%" /B

echo.
echo Ready for distribution!
pause