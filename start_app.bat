@echo off
setlocal
cd /d "%~dp0"
title Actual Text PDF - Setup and Launcher

echo ============================================
echo       ACTUAL TEXT PDF - START APPLICATION
echo ============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher was not found. Install Python 3.11 or newer and try again.
    pause
    exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -3 -m venv backend\.venv
    if errorlevel 1 goto :error
)

call "backend\.venv\Scripts\activate.bat"
echo Installing backend requirements...
pip install -r backend\requirements.txt
if errorlevel 1 goto :error

where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js and npm are required to build the frontend for source mode.
    echo Install Node.js LTS, then double-click start_app.bat again.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    pushd frontend
    call npm install
    if errorlevel 1 (popd & goto :error)
    popd
)

echo Building frontend...
pushd frontend
call npm run build
if errorlevel 1 (popd & goto :error)
popd

echo.
echo Launching application. Keep this window open.
python launcher.py
goto :end

:error
echo.
echo Setup or launch failed. Read the error above.
pause
exit /b 1

:end
endlocal
