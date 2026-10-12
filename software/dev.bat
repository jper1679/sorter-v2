@echo off
setlocal enabledelayedexpansion

title LEGO Sorter v2 - Windows Dev Launcher

:: Determine repository root directory
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "ROOT=%CD%"
popd

set "BACKEND_DIR=%ROOT%\software\sorter\backend"
set "FRONTEND_DIR=%ROOT%\software\sorter\frontend"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=all"

echo ===================================================
echo   LEGO Sorter V2 - Windows Dev Launcher
echo   Mode: %MODE%
echo ===================================================
echo.

:: Check for virtual environment in backend or root
set "VENV_ACTIVATE="
if exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%BACKEND_DIR%\.venv\Scripts\activate.bat"
) else if exist "%ROOT%\.venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%ROOT%\.venv\Scripts\activate.bat"
)

if /i "%MODE%"=="backend" goto :start_backend
if /i "%MODE%"=="frontend" goto :start_frontend
if /i "%MODE%"=="api" goto :start_api
if /i "%MODE%"=="all" goto :start_all

:start_all
echo [Launcher] Launching Backend and Frontend in separate windows...
echo.

if not "%VENV_ACTIVATE%"=="" (
    start "LEGO Sorter - Backend" cmd /k "cd /d "%BACKEND_DIR%" && call "%VENV_ACTIVATE%" && python supervisor.py --ui-port 0"
) else (
    start "LEGO Sorter - Backend" cmd /k "cd /d "%BACKEND_DIR%" && python supervisor.py --ui-port 0"
)

start "LEGO Sorter - Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npx pnpm dev"

echo [Launcher] Backend and Frontend processes launched!
echo [Launcher] Frontend Web UI: http://localhost:5173
echo [Launcher] Backend API: http://localhost:8000
echo.
pause
exit /b 0

:start_backend
echo [Launcher] Starting Backend...
cd /d "%BACKEND_DIR%"
if not "%VENV_ACTIVATE%"=="" call "%VENV_ACTIVATE%"
python supervisor.py --ui-port 0
exit /b 0

:start_api
echo [Launcher] Starting API-only Backend...
cd /d "%BACKEND_DIR%"
if not "%VENV_ACTIVATE%"=="" call "%VENV_ACTIVATE%"
python -m uvicorn server.api:app --host 127.0.0.1 --port 8000
exit /b 0

:start_frontend
echo [Launcher] Starting Frontend...
cd /d "%FRONTEND_DIR%"
npx pnpm dev
exit /b 0
