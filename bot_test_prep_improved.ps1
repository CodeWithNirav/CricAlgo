# IMPROVED BOT TEST PREP SCRIPT - PowerShell Version
# Enhanced version with better error handling, schema validation, and service checks

param(
    [string]$TelegramBotToken = $env:TELEGRAM_BOT_TOKEN,
    [string]$TelegramTestId1 = "693173957",
    [string]$TelegramTestId2 = "815804123",
    [string]$DatabaseUrl = "postgresql://postgres:postgres@localhost:5432/cricalgo",
    [string]$HttpBaseUrl = "http://localhost:8000",
    [string]$RedisUrl = "redis://localhost:6379/0",
    [string]$RunBotScript = "./app/bot/run_polling.py",
    [string]$Venv = ".venv",
    [bool]$UseSystemd = $false
)

$ErrorActionPreference = "Stop"

# Create artifacts directory
$TS = Get-Date -Format "yyyyMMddTHHmmssZ"
$ART = "artifacts/bot_test_prep_$TS"
New-Item -ItemType Directory -Path $ART -Force | Out-Null

function Log-Message {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = ">>> $Message"
    Write-Host $logMessage
    Add-Content -Path "$ART/run.log" -Value "$timestamp $logMessage"
}

function Log-Error {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $errorMessage = "ERROR: $Message"
    Write-Host $errorMessage -ForegroundColor Red
    Add-Content -Path "$ART/run.log" -Value "$timestamp $errorMessage"
    exit 1
}

Log-Message "Starting improved bot test prep at $TS"

# Validate configuration
if ([string]::IsNullOrEmpty($TelegramBotToken)) {
    Log-Error "TELEGRAM_BOT_TOKEN not set. Set the environment variable or pass as parameter."
}

if ([string]::IsNullOrEmpty($TelegramTestId2)) {
    $TelegramTestId2 = Read-Host "Enter second Telegram numeric ID (TEST_USER_ID2)"
}

Log-Message "Config summary: TEST_ID1=$TelegramTestId1 TEST_ID2=$TelegramTestId2 DB=$DatabaseUrl HTTP=$HttpBaseUrl"

# Pre-flight checks
Log-Message "0) Running pre-flight checks..."

# Check if psql is available
try {
    $null = Get-Command psql -ErrorAction Stop
    Log-Message "psql found - database operations will use psql"
} catch {
    Log-Message "WARNING: psql not found - database operations will use fallback methods"
}

# Check if Redis is accessible
try {
    $null = Get-Command redis-cli -ErrorAction Stop
    $redisTest = & redis-cli -u $RedisUrl ping 2>$null
    if ($redisTest -eq "PONG") {
        Log-Message "Redis is accessible"
    } else {
        Log-Message "WARNING: Redis not accessible at $RedisUrl - some features may not work"
    }
} catch {
    Log-Message "WARNING: redis-cli not found - cannot verify Redis connectivity"
}

# Check if bot script exists
if (-not (Test-Path $RunBotScript)) {
    Log-Error "Bot script not found at $RunBotScript"
}

# 1) Create/Upsert users and chat_map entries
Log-Message "1) Ensure users and chat_map are present in DB (upsert)"

$sqlUpsertUsers = @"
-- use standard functions; adjust for your DB if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO `$\$
BEGIN
  -- users table upsert with correct schema
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users') THEN
    -- upsert user 1
    INSERT INTO users (id, telegram_id, username, status, created_at)
    VALUES (uuid_generate_v4(), $TelegramTestId1, 'test_user_1', 'ACTIVE', now())
    ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username, status = EXCLUDED.status;
    -- upsert user 2
    INSERT INTO users (id, telegram_id, username, status, created_at)
    VALUES (uuid_generate_v4(), $TelegramTestId2, 'test_user_2', 'ACTIVE', now())
    ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username, status = EXCLUDED.status;
  END IF;
END
`$\$;
-- Upsert chat_map table with correct schema (chat_id as string)
DO `$\$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='chat_map') THEN
    INSERT INTO chat_map (id, user_id, chat_id)
    SELECT uuid_generate_v4()::text, u.id::text, u.telegram_id::text
    FROM users u WHERE u.telegram_id IN ($TelegramTestId1, $TelegramTestId2)
    ON CONFLICT (chat_id) DO UPDATE SET user_id = EXCLUDED.user_id;
  END IF;
END
`$\$;
"@

# Try to run SQL via psql
try {
    $null = Get-Command psql -ErrorAction Stop
    $sqlUpsertUsers | Out-File -FilePath "$ART/upsert_users.sql" -Encoding UTF8
    
    $env:PGPASSWORD = if ($env:PGPASSWORD) { $env:PGPASSWORD } else { "postgres" }
    
    Log-Message "Running SQL upsert to DB (psql)..."
    $psqlResult = & psql $DatabaseUrl -v ON_ERROR_STOP=1 -f "$ART/upsert_users.sql" 2>&1
    $psqlResult | Out-File -FilePath "$ART/psql_upsert_out.txt" -Encoding UTF8
    
    if ($LASTEXITCODE -eq 0) {
        Log-Message "Database upsert successful"
    } else {
        Log-Message "psql upsert returned non-zero. See $ART/psql_upsert_out.txt"
    }
} catch {
    Log-Message "psql not found - attempting fallback via admin HTTP API"
    if ($env:ADMIN_TOKEN) {
        foreach ($id in @($TelegramTestId1, $TelegramTestId2)) {
            try {
                $body = @{
                    telegram_id = [int]$id
                    username = "bot_seed_$id"
                    status = "ACTIVE"
                } | ConvertTo-Json
                
                Invoke-RestMethod -Uri "$HttpBaseUrl/api/v1/admin/users" -Method Post -Headers @{
                    "Authorization" = "Bearer $env:ADMIN_TOKEN"
                    "Content-Type" = "application/json"
                } -Body $body -OutFile "$ART/user_seed_$id.json" -ErrorAction SilentlyContinue
            } catch {
                Log-Message "Failed to create user $id via API"
            }
        }
    } else {
        Log-Message "No ADMIN_TOKEN provided, skipping HTTP fallback. Please ensure DB has users."
    }
}

# 2) Verify chat_map entries
Log-Message "2) Verifying chat_map rows exist"

$pythonCheckScript = @"
import os,sys
from urllib.parse import urlparse
url=os.environ.get("DATABASE_URL", "$DatabaseUrl")
out={"database_url": url, "chatmap_ok": False}
try:
    import sqlalchemy as sa
    engine=sa.create_engine(url)
    with engine.connect() as conn:
        q = "SELECT count(*) FROM information_schema.tables WHERE table_name='chat_map'"
        if conn.execute(sa.text(q)).scalar():
            res = conn.execute(sa.text("SELECT count(*) FROM chat_map WHERE chat_id IN (:a,:b)"), {"a":str($TelegramTestId1),"b":str($TelegramTestId2)}).scalar()
            out["chatmap_count"] = int(res)
            out["chatmap_ok"] = (res>=1)
        else:
            out["chatmap_exists"]=False
except Exception as e:
    out["error"]=str(e)
print(out)
"@

$pythonCheckScript | python3 > "$ART/check_chatmap.json" 2>&1

Log-Message "Check chat_map results:"
Get-Content "$ART/check_chatmap.json" | Write-Host
Add-Content -Path "$ART/run.log" -Value (Get-Content "$ART/check_chatmap.json")

# 3) Create environment file
Log-Message "3) Creating environment file"
$envFile = ".env.local.bot"
@"
TELEGRAM_BOT_TOKEN=$TelegramBotToken
DATABASE_URL=$DatabaseUrl
REDIS_URL=$RedisUrl
"@ | Out-File -FilePath $envFile -Encoding UTF8

Log-Message "Wrote environment variables to $envFile"

# 4) Start bot in background
Log-Message "4) Starting bot in polling mode (background). Logs -> $ART/bot_polling.log"

# Stop existing bot processes
Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*run_polling.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

if ($UseSystemd) {
    Log-Message "USE_SYSTEMD=true - attempting systemctl restart cricalgo-bot.service"
    try {
        & sudo systemctl restart cricalgo-bot.service
    } catch {
        Log-Message "systemctl restart failed (service may not exist)"
    }
} else {
    # Start bot with appropriate Python
    $pythonExe = if (Test-Path "$Venv/bin/python") { "$Venv/bin/python" } elseif (Test-Path "$Venv/Scripts/python.exe") { "$Venv/Scripts/python.exe" } else { "python3" }
    
    Start-Process -FilePath $pythonExe -ArgumentList $RunBotScript -RedirectStandardOutput "$ART/bot_polling.log" -RedirectStandardError "$ART/bot_polling.log" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

# 5) Check bot logs
Start-Sleep -Seconds 4
if (Test-Path "$ART/bot_polling.log" -and (Get-Item "$ART/bot_polling.log").Length -gt 0) {
    Log-Message "Bot log (last 40 lines):"
    Get-Content "$ART/bot_polling.log" | Select-Object -Last 40 | Write-Host
    Add-Content -Path "$ART/run.log" -Value (Get-Content "$ART/bot_polling.log" | Select-Object -Last 40)
} else {
    Log-Message "Bot log empty or not created yet; check $ART/bot_polling.log"
}

# 6) Test Telegram API
Log-Message "6) Testing Telegram API"
try {
    $tgMe = Invoke-RestMethod -Uri "https://api.telegram.org/bot$TelegramBotToken/getMe"
    $tgMe | ConvertTo-Json | Out-File -FilePath "$ART/tg_getme.json" -Encoding UTF8
    
    if ($tgMe.ok) {
        Log-Message "Telegram token valid — getMe OK"
        Log-Message "Bot username: @$($tgMe.result.username)"
        $botUsername = $tgMe.result.username
    } else {
        Log-Message "Warning: Telegram token appears invalid; see $ART/tg_getme.json"
        $botUsername = "unknown"
    }
} catch {
    Log-Message "Warning: Failed to test Telegram API"
    $botUsername = "unknown"
}

# 7) Test webhook endpoint
Log-Message "7) Testing webhook endpoint"
try {
    $webhookBody = @{
        tx_hash = "test-$TS"
        telegram_id = [int]$TelegramTestId1
        amount = "20.0"
        confirmations = 12
    } | ConvertTo-Json
    
    $webhookResponse = Invoke-RestMethod -Uri "$HttpBaseUrl/api/v1/webhooks/bep20" -Method Post -Body $webhookBody -ContentType "application/json" -ErrorAction SilentlyContinue
    $webhookResponse | ConvertTo-Json | Out-File -FilePath "$ART/webhook_test.json" -Encoding UTF8
    Log-Message "Webhook endpoint is responding"
} catch {
    Log-Message "WARNING: Webhook endpoint not responding (server may not be running)"
    @{ error = $_.Exception.Message } | ConvertTo-Json | Out-File -FilePath "$ART/webhook_test.json" -Encoding UTF8
}

# 8) Create test instructions
Log-Message "8) Creating test instructions"
$nextSteps = @"
Bot test prep finished at $TS.

How to test from two Telegram accounts:
- From each Telegram account (IDs: $TelegramTestId1 and $TelegramTestId2):
  1) Open chat with @$botUsername (if available)
  2) Send: /start
  3) Send: /balance (to check wallet)
  4) Send: /contests (to see available contests)
  5) Use inline buttons to join contests

Test deposit notification (simulates blockchain webhook):
Invoke-RestMethod -Uri '$HttpBaseUrl/api/v1/webhooks/bep20' -Method Post -Body (@{
    tx_hash = "test-$TS-deposit"
    telegram_id = $TelegramTestId1
    amount = "20.0"
    confirmations = 12
} | ConvertTo-Json) -ContentType "application/json"

Test withdrawal notification:
Invoke-RestMethod -Uri '$HttpBaseUrl/api/v1/webhooks/bep20' -Method Post -Body (@{
    tx_hash = "test-$TS-withdrawal"
    telegram_id = $TelegramTestId1
    amount = "5.0"
    confirmations = 12
    status = "confirmed"
} | ConvertTo-Json) -ContentType "application/json"

Check logs:
- Bot runtime log: $ART/bot_polling.log
- DB check output: $ART/psql_upsert_out.txt (if psql used)
- Webhook test results: $ART/webhook_test.json
- Diagnostic artifacts: $ART

Troubleshooting:
- If bot doesn't respond: Check $ART/bot_polling.log for errors
- If webhook fails: Ensure main server is running on $HttpBaseUrl
- If database issues: Check $ART/psql_upsert_out.txt
- If Redis issues: Check Redis is running on $RedisUrl
"@

$nextSteps | Out-File -FilePath "$ART/next_steps.txt" -Encoding UTF8
Log-Message "Wrote next_steps to $ART/next_steps.txt"

# 9) Package artifacts
Log-Message "9) Packaging artifacts"
try {
    Compress-Archive -Path $ART -DestinationPath "$ART.zip" -Force
    Log-Message "Artifacts packaged: $ART.zip"
} catch {
    Log-Message "Failed to package artifacts, but they are available in $ART"
}

Write-Host "IMPROVED BOT TEST PREP COMPLETE. Artifacts: $ART.zip" -ForegroundColor Green
Write-Host "Follow the instructions in $ART/next_steps.txt to test on your two Telegram accounts." -ForegroundColor Yellow
