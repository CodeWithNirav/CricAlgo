@echo off
REM CricAlgo Smoke Test Runner for Windows
REM This batch file sets up environment variables and runs the smoke test

echo CricAlgo Smoke Test Runner
echo ========================

REM Check if required environment variables are set
if "%HTTP%"=="" (
    echo ERROR: HTTP environment variable not set
    echo Please set HTTP=http://localhost:8000
    exit /b 1
)

if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo ERROR: TELEGRAM_BOT_TOKEN environment variable not set
    exit /b 1
)

if "%ADMIN_TOKEN%"=="" (
    echo ERROR: ADMIN_TOKEN environment variable not set
    exit /b 1
)

if "%USER1_TELEGRAM_ID%"=="" (
    echo ERROR: USER1_TELEGRAM_ID environment variable not set
    exit /b 1
)

if "%USER2_TELEGRAM_ID%"=="" (
    echo ERROR: USER2_TELEGRAM_ID environment variable not set
    exit /b 1
)

echo Environment variables validated
echo HTTP: %HTTP%
echo Bot Token: %TELEGRAM_BOT_TOKEN:~0,10%...
echo Admin Token: %ADMIN_TOKEN:~0,10%...
echo User 1 ID: %USER1_TELEGRAM_ID%
echo User 2 ID: %USER2_TELEGRAM_ID%

echo.
echo Starting smoke test...
echo.

REM Run the improved smoke test script using Git Bash or WSL
if exist "C:\Program Files\Git\bin\bash.exe" (
    echo Using Git Bash...
    "C:\Program Files\Git\bin\bash.exe" scripts/improved_smoke_test.sh
) else if exist "C:\Windows\System32\wsl.exe" (
    echo Using WSL...
    wsl bash scripts/improved_smoke_test.sh
) else (
    echo ERROR: Neither Git Bash nor WSL found
    echo Please install Git for Windows or WSL to run the smoke test
    echo Alternatively, run the script manually in a Unix-like environment
    exit /b 1
)

echo.
echo Smoke test completed
echo Check the artifacts directory for results
