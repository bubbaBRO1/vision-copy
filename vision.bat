@echo off
setlocal EnableExtensions EnableDelayedExpansion
title VISION OSINT Workstation

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

:menu
cls
echo.
echo ============================================================
echo  VISION OSINT WORKSTATION
echo ============================================================
echo  Root: %ROOT%
echo.
echo  [1] Start everything with Docker
echo  [2] Stop Docker stack
echo  [3] Restart Docker stack
echo  [4] Show Docker status
echo  [5] Tail Docker logs
echo  [6] Open website and health page
echo  [7] Run backend tests
echo  [8] Run frontend tests and build
echo  [9] Run all verification
echo  [A] First-time setup only
echo  [0] Exit
echo.
set /p "CHOICE=Choose: "

if /i "%CHOICE%"=="1" goto start
if /i "%CHOICE%"=="2" goto stop
if /i "%CHOICE%"=="3" goto restart
if /i "%CHOICE%"=="4" goto status
if /i "%CHOICE%"=="5" goto logs
if /i "%CHOICE%"=="6" goto open
if /i "%CHOICE%"=="7" goto backend_tests
if /i "%CHOICE%"=="8" goto frontend_tests
if /i "%CHOICE%"=="9" goto verify_all
if /i "%CHOICE%"=="A" goto setup
if /i "%CHOICE%"=="0" exit /b 0
goto menu

:setup
call :ensure_env
call :force_open_registration
call :ensure_frontend_deps
echo.
echo [OK] First-time setup finished.
pause
goto menu

:start
call :ensure_env
call :force_open_registration
cd /d "%ROOT%"
echo.
echo [VISION] Starting Docker stack...
docker compose up --build -d
if errorlevel 1 goto docker_error
echo.
echo [VISION] Waiting for services to settle...
timeout /t 8 /nobreak >nul
docker compose ps
call :open_urls
echo.
echo [OK] VISION is starting at http://localhost
pause
goto menu

:stop
cd /d "%ROOT%"
docker compose down
pause
goto menu

:restart
cd /d "%ROOT%"
docker compose down
docker compose up --build -d
if errorlevel 1 goto docker_error
timeout /t 8 /nobreak >nul
docker compose ps
call :open_urls
pause
goto menu

:status
cd /d "%ROOT%"
docker compose ps
echo.
echo Website:      http://localhost
echo Health:       http://localhost/api/system/health
echo API docs:     http://localhost/api/docs
pause
goto menu

:logs
cd /d "%ROOT%"
echo Press Ctrl+C to stop following logs.
docker compose logs -f --tail=80
pause
goto menu

:open
call :open_urls
goto menu

:backend_tests
cd /d "%ROOT%"
if exist "backend\venv\Scripts\python.exe" (
  backend\venv\Scripts\python.exe -m pytest backend\tests -q
) else (
  python -m pytest backend\tests -q
)
pause
goto menu

:frontend_tests
call :ensure_frontend_deps
cd /d "%ROOT%\frontend"
npm test -- --run
if errorlevel 1 goto frontend_error
npm run build
if errorlevel 1 goto frontend_error
pause
goto menu

:verify_all
cd /d "%ROOT%"
if exist "backend\venv\Scripts\python.exe" (
  backend\venv\Scripts\python.exe -m pytest backend\tests -q
) else (
  python -m pytest backend\tests -q
)
if errorlevel 1 goto backend_error
call :ensure_frontend_deps
cd /d "%ROOT%\frontend"
npm test -- --run
if errorlevel 1 goto frontend_error
npm run build
if errorlevel 1 goto frontend_error
cd /d "%ROOT%"
docker compose config
if errorlevel 1 goto docker_error
echo.
echo [OK] Verification complete.
pause
goto menu

:ensure_env
cd /d "%ROOT%"
if not exist ".env" (
  echo [VISION] Creating .env from .env.example...
  copy ".env.example" ".env" >nul
)
exit /b 0

:force_open_registration
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" (
  echo [WARN] PowerShell was not found. Set OPEN_REGISTRATION=true in .env if signup is blocked.
  exit /b 0
)
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Join-Path '%ROOT%' '.env';" ^
  "$text = Get-Content -Raw -LiteralPath $p;" ^
  "if ($text -match '(?m)^OPEN_REGISTRATION=') { $text = $text -replace '(?m)^OPEN_REGISTRATION=.*$', 'OPEN_REGISTRATION=true' } else { $text += \"`r`nOPEN_REGISTRATION=true`r`n\" };" ^
  "Set-Content -LiteralPath $p -Value $text -NoNewline"
exit /b 0

:ensure_frontend_deps
if not exist "%ROOT%\frontend\node_modules" (
  cd /d "%ROOT%\frontend"
  npm install
)
exit /b 0

:open_urls
start "" "http://localhost"
start "" "http://localhost/api/system/health"
exit /b 0

:docker_error
echo.
echo [ERROR] Docker command failed. Make sure Docker Desktop is running.
pause
goto menu

:backend_error
echo.
echo [ERROR] Backend tests failed.
pause
goto menu

:frontend_error
echo.
echo [ERROR] Frontend command failed.
pause
goto menu
