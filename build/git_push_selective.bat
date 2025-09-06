@echo off
echo Selective Git Push - Essential Files Only

cd /d "C:\Newbies"

echo Adding essential Python files...
git add *.py

echo Adding documentation...
git add *.md

echo Adding assets...
git add assets/

echo Adding build system...
git add build/

echo Adding requirements...
git add requirements.txt

echo Adding gitignore...
git add .gitignore

echo.
echo Files to be committed:
git status --porcelain

echo.
echo Committing changes...
git commit -m "Update source code and build system - v1.0.0"

echo.
echo Pushing to remote...
git push origin main
if errorlevel 1 git push origin master

echo.
echo SUCCESS: Essential files pushed to Git!
pause