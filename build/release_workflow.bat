@echo off
echo NewbiesBot Release Workflow

echo [1/4] Checking git status...
cd /d "C:\Newbies"
git status

echo.
echo [2/4] Adding and committing changes...
git add .
git commit -m "Release v1.0.0 - Build system and executable ready"

echo.
echo [3/4] Pushing to GitHub...
git push origin main
if errorlevel 1 git push origin master

echo.
echo [4/4] Creating release package...
call build\deploy_complete.bat

echo.
echo WORKFLOW COMPLETE!
echo - Source code pushed to GitHub
echo - Release package created locally
echo - Ready for GitHub Release creation
pause