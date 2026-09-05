@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python was not found on this PC.
        echo Install it from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" on the first screen, then run this again.
        pause
        exit /b 1
    )
    py install_mod.py %*
    pause
    exit /b
)

python install_mod.py %*
pause
