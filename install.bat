@echo off
rem Installs the three libraries the helper needs. Run it once, after installing Python.
python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found.
    echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer,
    echo then run this file again.
    pause
    exit /b 1
)
python -m pip install numpy opencv-python mss
if errorlevel 1 (
    echo.
    echo Installing failed. Check your internet connection and run this file again.
) else (
    echo.
    echo Done. Double-click start_helper.bat to start the helper.
)
pause
