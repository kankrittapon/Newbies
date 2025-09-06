@echo off
echo Checking Python versions...

echo.
echo === Available Python versions ===
py -0

echo.
echo === Testing Python 3.12 ===
py -3.12 --version
if errorlevel 1 (
    echo ERROR: Python 3.12 not found
) else (
    echo SUCCESS: Python 3.12 found
)

echo.
echo === Default Python ===
python --version

pause