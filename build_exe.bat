@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 goto :fatal

title Build Actual Text PDF - Single EXE

echo ============================================
echo    BUILD ACTUAL TEXT PDF - SINGLE EXE
echo ============================================
echo.

REM Check required build tools.
where py >nul 2>&1
if errorlevel 1 goto :python_missing

where npm >nul 2>&1
if errorlevel 1 goto :npm_missing

REM Create a virtual environment if it does not already exist.
if exist "backend\.venv\Scripts\python.exe" goto :venv_ready

echo [1/6] Creating build virtual environment...
py -3 -m venv "backend\.venv"
if errorlevel 1 goto :fatal

:venv_ready
set "PYTHON_EXE=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" goto :venv_python_missing

echo [2/6] Installing backend and PyInstaller requirements...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :fatal
"%PYTHON_EXE%" -m pip install -r "backend\requirements.txt" -r "requirements-build.txt"
if errorlevel 1 goto :fatal

echo [3/6] Installing frontend dependencies...
pushd "frontend"
if errorlevel 1 goto :fatal
call npm install
if errorlevel 1 goto :frontend_failed

echo [4/6] Building React frontend...
call npm run build
if errorlevel 1 goto :frontend_failed
popd

if not exist "frontend\dist\index.html" goto :frontend_build_missing

echo [5/6] Cleaning previous PyInstaller output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "ActualTextPDF.spec" del /q "ActualTextPDF.spec"

echo [6/6] Building one-file Windows executable...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onefile --console ^
  --name ActualTextPDF ^
  --paths "backend" ^
  --add-data "frontend\dist;frontend_dist" ^
  --collect-all uvicorn ^
  --collect-all fastapi ^
  --collect-all starlette ^
  --collect-all fitz ^
  --collect-all pymupdf ^
  --hidden-import multipart ^
  --hidden-import app.main ^
  --hidden-import app.routes.pdf_routes ^
  --hidden-import app.services.pdf_service ^
  launcher.py
if errorlevel 1 goto :fatal

if not exist "dist\ActualTextPDF.exe" goto :exe_missing

echo.
echo ============================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ============================================
echo.
echo Single-file executable:
echo   %CD%\dist\ActualTextPDF.exe
echo.
echo Copy only ActualTextPDF.exe to another compatible Windows PC.
echo The first launch can take longer while PyInstaller extracts bundled files.
echo Keep the EXE in a writable folder and keep its console window open.
echo.
echo IMPORTANT: Build on Windows. Test on a separate Windows PC before distribution.
echo.
pause
exit /b 0

:python_missing
echo ERROR: Python Launcher py.exe was not found.
echo Install Python 3.11 or newer and enable the Python Launcher.
goto :failed

:npm_missing
echo ERROR: npm was not found.
echo Install Node.js LTS, then reopen Command Prompt.
goto :failed

:venv_python_missing
echo ERROR: The virtual environment Python executable was not created.
goto :failed

:frontend_build_missing
echo ERROR: frontend\dist\index.html was not generated.
goto :failed

:exe_missing
echo ERROR: PyInstaller did not create dist\ActualTextPDF.exe.
goto :failed

:frontend_failed
echo ERROR: Frontend dependency installation or build failed.
popd
goto :failed

:fatal
echo ERROR: A build command failed. Check the error shown above.

:failed
echo.
echo BUILD FAILED. Do not distribute an incomplete executable.
echo.
pause
exit /b 1
