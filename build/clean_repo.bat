@echo off
echo Cleaning repository...

cd /d "C:\Newbies"

echo Removing build outputs...
if exist "NewbiesBot.exe" del "NewbiesBot.exe"
if exist "NewbiesBot.dist" rmdir /s /q "NewbiesBot.dist"
if exist "NewbiesBot.build" rmdir /s /q "NewbiesBot.build"

echo Removing release packages...
for /d %%i in (release_*) do rmdir /s /q "%%i"
for /d %%i in (NewbiesBot_*) do rmdir /s /q "%%i"

echo Removing logs...
if exist "logs" rmdir /s /q "logs"
if exist "nuitka-crash-report.xml" del "nuitka-crash-report.xml"

echo Removing user data...
if exist "chrome_profiles" rmdir /s /q "chrome_profiles"
if exist "extension" rmdir /s /q "extension"
if exist "config" rmdir /s /q "config"

echo Removing Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s *.pyc 2>nul

echo.
echo Repository cleaned!
echo Ready for git operations.
pause