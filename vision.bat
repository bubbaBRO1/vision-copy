@echo off
setlocal EnableDelayedExpansion
title VISION OSINT Platform

:menu
cls
echo.
echo  ██╗   ██╗██╗███████╗██╗ ██████╗ ███╗   ██╗
echo  ██║   ██║██║██╔════╝██║██╔═══██╗████╗  ██║
echo  ██║   ██║██║███████╗██║██║   ██║██╔██╗ ██║
echo  ╚██╗ ██╔╝██║╚════██║██║██║   ██║██║╚██╗██║
echo   ╚████╔╝ ██║███████║██║╚██████╔╝██║ ╚████║
echo    ╚═══╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
echo.
echo  OSINT Platform Launcher
echo  ─────────────────────────────────────────────
echo  [1] Docker  — Full stack (prod-like, all 6 services)
echo  [2] Dev     — Local backend + frontend (hot reload)
echo  [3] Dev+DB  — Local dev with Docker postgres+redis
echo  [4] Logs    — Tail Docker logs
echo  [5] Stop    — Stop all Docker containers
echo  [6] Reset   — Stop + remove volumes (DESTROYS DATA)
echo  [7] Shell   — Open backend container shell
echo  [8] Migrate — Run Alembic migrations
echo  [9] Test    — Run backend pytest + frontend build check
echo  [0] Exit
echo.
set /p choice=" Choose: "

if "%choice%"=="1" goto docker_full
if "%choice%"=="2" goto dev_local
if "%choice%"=="3" goto dev_docker_deps
if "%choice%"=="4" goto logs
if "%choice%"=="5" goto stop
if "%choice%"=="6" goto reset
if "%choice%"=="7" goto shell
if "%choice%"=="8" goto migrate
if "%choice%"=="9" goto test
if "%choice%"=="0" exit /b
goto menu

:: ─────────────────────────────────────────────
:docker_full
cls
echo [VISION] Starting full Docker stack...
echo.

:: Check .env exists
if not exist "%~dp0.env" (
    echo [WARN] .env not found — copying .env.example
    copy "%~dp0.env.example" "%~dp0.env" >nul
    echo [WARN] Edit .env and set JWT_SECRET + DB password before production use.
    pause
)

cd /d "%~dp0"
docker compose up --build -d

if errorlevel 1 (
    echo [ERROR] Docker compose failed. Is Docker Desktop running?
    pause
    goto menu
)

echo.
echo [OK] Services starting. Waiting for health checks...
timeout /t 10 /nobreak >nul

:: Print service status
docker compose ps

echo.
echo  ┌─────────────────────────────────────────┐
echo  │  Frontend:  http://localhost             │
echo  │  Backend:   http://localhost/api         │
echo  │  API Docs:  http://localhost/api/docs    │
echo  │  Ollama:    http://localhost:11434       │
echo  └─────────────────────────────────────────┘
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:: ─────────────────────────────────────────────
:dev_local
cls
echo [VISION] Starting local dev servers...
echo.
echo Requires: Python 3.11+, Node 18+, PostgreSQL, Redis running locally
echo.

:: Check .env exists in backend
if not exist "%~dp0backend\.env" (
    if exist "%~dp0.env" (
        copy "%~dp0.env" "%~dp0backend\.env" >nul
        echo [INFO] Copied .env to backend/.env
    ) else (
        echo [WARN] No .env found. Copy .env.example to backend/.env and configure it.
        pause
        goto menu
    )
)

:: Check venv
if not exist "%~dp0backend\venv\Scripts\activate.bat" (
    echo [INFO] Creating Python venv...
    cd /d "%~dp0backend"
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    echo [INFO] Using existing venv
)

:: Start backend in new window
echo [INFO] Starting backend on :8000...
start "VISION Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && set PYTHONPATH=%~dp0backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

:: Install frontend deps if needed
if not exist "%~dp0frontend\node_modules" (
    echo [INFO] Installing frontend deps...
    cd /d "%~dp0frontend"
    npm install
)

:: Start frontend in new window
echo [INFO] Starting frontend on :5173...
start "VISION Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo  ┌─────────────────────────────────────────┐
echo  │  Frontend:  http://localhost:5173        │
echo  │  Backend:   http://localhost:8000        │
echo  │  API Docs:  http://localhost:8000/docs   │
echo  └─────────────────────────────────────────┘
echo.
echo Two new windows opened. Close them to stop dev servers.
pause >nul
goto menu

:: ─────────────────────────────────────────────
:dev_docker_deps
cls
echo [VISION] Starting infra only (postgres + redis) via Docker...
echo.

cd /d "%~dp0"
docker compose up -d vision-postgres vision-redis

echo.
echo [OK] postgres:5432 and redis:6379 running in Docker.
echo.
echo Now starting local dev servers (backend + frontend)...
echo.

if not exist "%~dp0backend\.env" (
    copy "%~dp0.env.example" "%~dp0backend\.env" >nul
    echo [WARN] Created backend/.env from .env.example — edit it now.
    notepad "%~dp0backend\.env"
)

if not exist "%~dp0backend\venv\Scripts\activate.bat" (
    echo [INFO] Creating Python venv...
    cd /d "%~dp0backend"
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)

start "VISION Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && set DATABASE_URL=postgresql+asyncpg://vision:changeme@localhost:5432/vision && set REDIS_URL=redis://localhost:6379 && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

if not exist "%~dp0frontend\node_modules" (
    cd /d "%~dp0frontend"
    npm install
)

start "VISION Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo  ┌─────────────────────────────────────────────────────┐
echo  │  Frontend:  http://localhost:5173                   │
echo  │  Backend:   http://localhost:8000                   │
echo  │  Postgres:  localhost:5432 (Docker)                 │
echo  │  Redis:     localhost:6379 (Docker)                 │
echo  └─────────────────────────────────────────────────────┘
echo.
pause >nul
goto menu

:: ─────────────────────────────────────────────
:logs
cls
echo [VISION] Tailing Docker logs (Ctrl+C to stop)...
echo.
cd /d "%~dp0"
docker compose logs -f --tail=50
goto menu

:: ─────────────────────────────────────────────
:stop
cls
echo [VISION] Stopping all containers...
cd /d "%~dp0"
docker compose down
echo [OK] Stopped.
pause >nul
goto menu

:: ─────────────────────────────────────────────
:reset
cls
echo.
echo  WARNING: This will DESTROY all data — postgres volume, redis volume, uploads.
echo  Type RESET to confirm, anything else to cancel.
echo.
set /p confirm=" Confirm: "
if /i not "%confirm%"=="RESET" (
    echo Cancelled.
    pause >nul
    goto menu
)
cd /d "%~dp0"
docker compose down -v --remove-orphans
echo [OK] Volumes destroyed.
pause >nul
goto menu

:: ─────────────────────────────────────────────
:shell
cls
echo [VISION] Opening backend container shell...
docker exec -it vision-backend /bin/bash
goto menu

:: ─────────────────────────────────────────────
:test
cls
echo [VISION] Running tests...
echo.

set BACKEND_OK=0
set FRONTEND_OK=0

:: Backend pytest
if exist "%~dp0backend\venv\Scripts\activate.bat" (
    cd /d "%~dp0backend"
    call venv\Scripts\activate.bat
    echo [TEST] Running backend pytest...
    python -m pytest tests/ -v --tb=short 2>&1
    if not errorlevel 1 set BACKEND_OK=1
) else (
    echo [WARN] No backend venv found — skipping pytest
    set BACKEND_OK=1
)

:: Frontend build check
if exist "%~dp0frontend\node_modules" (
    echo.
    echo [TEST] Running frontend build check...
    cd /d "%~dp0frontend"
    call npm run build 2>&1
    if not errorlevel 1 set FRONTEND_OK=1
) else (
    echo [WARN] No frontend node_modules — skipping build check
    set FRONTEND_OK=1
)

echo.
if "%BACKEND_OK%"=="1" (echo [OK]   Backend tests passed) else (echo [FAIL] Backend tests failed)
if "%FRONTEND_OK%"=="1" (echo [OK]   Frontend build passed) else (echo [FAIL] Frontend build failed)
echo.
pause >nul
goto menu

:: ─────────────────────────────────────────────
:migrate
cls
echo [VISION] Running Alembic migrations...
echo.
cd /d "%~dp0"

:: Try Docker first
docker inspect vision-backend >nul 2>&1
if not errorlevel 1 (
    docker exec vision-backend alembic upgrade head
    echo [OK] Migrations applied via Docker container.
) else (
    :: Fall back to local venv
    if exist "%~dp0backend\venv\Scripts\activate.bat" (
        cd /d "%~dp0backend"
        call venv\Scripts\activate.bat
        alembic upgrade head
        echo [OK] Migrations applied via local venv.
    ) else (
        echo [ERROR] Neither Docker container nor local venv found.
    )
)
pause >nul
goto menu
