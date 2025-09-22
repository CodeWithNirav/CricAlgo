@echo off
REM Simple batch script to manage CricAlgo services

if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="status" goto status
if "%1"=="logs" goto logs
goto help

:start
echo 🚀 Starting CricAlgo services...
docker-compose up -d
if %errorlevel% equ 0 (
    echo ✅ Services started successfully!
    echo 📊 Checking service status...
    timeout /t 5 /nobreak >nul
    goto status
) else (
    echo ❌ Failed to start services
    exit /b 1
)
goto end

:stop
echo 🛑 Stopping CricAlgo services...
docker-compose down
if %errorlevel% equ 0 (
    echo ✅ Services stopped successfully!
) else (
    echo ❌ Failed to stop services
    exit /b 1
)
goto end

:restart
echo 🔄 Restarting CricAlgo services...
call :stop
timeout /t 2 /nobreak >nul
call :start
goto end

:status
echo 📊 Service Status:
echo.
docker-compose ps
echo.
echo 🌐 Service URLs:
echo    Admin Dashboard: http://localhost:8000/admin
echo    API Docs: http://localhost:8000/docs
echo    Health Check: http://localhost:8000/api/v1/health
echo    Database: localhost:5432
echo    Redis: localhost:6379
goto end

:logs
echo 📋 Showing recent logs...
echo.
docker-compose logs --tail=20
goto end

:help
echo 💡 Usage: manage_services.bat [start^|stop^|restart^|status^|logs]
echo.
echo Commands:
echo   start   - Start all services
echo   stop    - Stop all services
echo   restart - Restart all services
echo   status  - Show service status
echo   logs    - Show recent logs
goto end

:end
