@echo off
echo Pushing updates to Git...

REM Go to project root
cd /d "C:\Newbies"

REM Check git status
echo Checking git status...
git status

echo.
echo Adding all changes...
git add .

echo.
echo Committing changes...
git commit -m "Update build system and deploy scripts - v1.0.0"

echo.
echo Pushing to remote...
git push origin main

if errorlevel 1 (
    echo Trying 'master' branch...
    git push origin master
)

echo.
echo SUCCESS: Git push completed!
pause