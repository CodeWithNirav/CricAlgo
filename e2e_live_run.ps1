# E2E Live Test Script for PowerShell
param(
    [string]$HttpUrl = "http://localhost:8000",
    [string]$AdminUsername = "admin",
    [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

# Create timestamp and artifact directory
$TS = Get-Date -Format "yyyyMMddTHHmmssZ"
$ART = "artifacts\e2e_live_$TS"
New-Item -ItemType Directory -Path $ART -Force | Out-Null

function Log {
    param([string]$Message)
    $LogMessage = ">>> $Message"
    Write-Host $LogMessage
    Add-Content -Path "$ART\run.log" -Value $LogMessage
}

# Create git branch
$BR = "test/e2e-live-$TS"
try {
    git checkout -b $BR
} catch {
    git switch -c $BR
}

Log "1) Check health"
$HealthCheck = $false
for ($i = 1; $i -le 20; $i++) {
    try {
        $Response = Invoke-WebRequest -Uri "$HttpUrl/api/v1/health" -UseBasicParsing -TimeoutSec 5
        if ($Response.StatusCode -eq 200) {
            Log "app healthy"
            $HealthCheck = $true
            break
        }
    } catch {
        Log "waiting... ($i/20)"
        Start-Sleep -Seconds 3
    }
}

if (-not $HealthCheck) {
    Log "ERROR: App health check failed after 20 attempts"
    exit 1
}

Log "2) Admin login"
try {
    $LoginBody = @{
        username = $AdminUsername
        password = $AdminPassword
    } | ConvertTo-Json

    $LoginResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/admin/login" -Method POST -Body $LoginBody -ContentType "application/json" -UseBasicParsing
    $LoginData = $LoginResponse.Content | ConvertFrom-Json
    $TOKEN = $LoginData.access_token
    $TOKEN | Out-File -FilePath "$ART\admin_token.txt" -Encoding UTF8
    Log "Admin login successful"
} catch {
    Log "ERROR: Admin login failed - $_"
    exit 1
}

Log "3) Create match & contest"
try {
    # Create match
    $MatchBody = @{
        title = "E2E Live Match"
        start_time = "2030-01-01T00:00:00Z"
    } | ConvertTo-Json

    $MatchResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/admin/matches" -Method POST -Body $MatchBody -ContentType "application/json" -Headers @{"Authorization" = "Bearer $TOKEN"} -UseBasicParsing
    $MatchData = $MatchResponse.Content | ConvertFrom-Json
    $MatchData | ConvertTo-Json | Out-File -FilePath "$ART\match.json" -Encoding UTF8
    $MID = $MatchData.match.id
    Log "Match created with ID: $MID"

    # Create contest
    $ContestBody = @{
        title = "E2E Live Contest"
        entry_fee = "5.0"
        max_players = 100
        prize_structure = @{
            "1" = 4.5
        }
    } | ConvertTo-Json

    $ContestResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/admin/matches/$MID/contests" -Method POST -Body $ContestBody -ContentType "application/json" -Headers @{"Authorization" = "Bearer $TOKEN"} -UseBasicParsing
    $ContestData = $ContestResponse.Content | ConvertFrom-Json
    $ContestData | ConvertTo-Json | Out-File -FilePath "$ART\contest.json" -Encoding UTF8
    $CID = $ContestData.contest.id
    Log "Contest created with ID: $CID"
} catch {
    Log "ERROR: Failed to create match/contest - $_"
    exit 1
}

Log "4) Prompt user: please open Telegram and send /start to bot now"
Write-Host ">>> Open your Telegram client, send /start to the bot. Waiting 20s..." | Tee-Object -FilePath "$ART\run.log" -Append
Start-Sleep -Seconds 20

Log "5) Create deposit via webhook"
try {
    $TX = "e2e-live-$TS"
    $WebhookBody = @{
        tx_hash = $TX
        user_id = "f2264ff0-d342-4620-860a-f5d9139ecc4a"
        amount = "20.0"
        confirmations = 12
    } | ConvertTo-Json

    $WebhookResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/webhooks/bep20" -Method POST -Body $WebhookBody -ContentType "application/json" -UseBasicParsing
    $WebhookResponse.Content | Out-File -FilePath "$ART\webhook.json" -Encoding UTF8
    Log "Deposit webhook sent"
} catch {
    Log "ERROR: Deposit webhook failed - $_"
}

Start-Sleep -Seconds 10  # allow Celery worker to process

Log "6) Join contest (simulate bot callback via API)"
try {
    $JoinBody = @{
        telegram_id = 693173957
    } | ConvertTo-Json

    $JoinResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/contests/$CID/join" -Method POST -Body $JoinBody -ContentType "application/json" -UseBasicParsing
    $JoinResponse.Content | Out-File -FilePath "$ART\join.json" -Encoding UTF8
    Log "Contest join attempted"
} catch {
    Log "ERROR: Contest join failed - $_"
}

Log "7) Settle contest"
try {
    $SettleResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/admin/contests/$CID/settle" -Method POST -Body "{}" -ContentType "application/json" -Headers @{"Authorization" = "Bearer $TOKEN"} -UseBasicParsing
    $SettleResponse.Content | Out-File -FilePath "$ART\settle.json" -Encoding UTF8
    Log "Contest settled"
} catch {
    Log "ERROR: Contest settlement failed - $_"
}

Log "8) Create withdrawal & approve"
try {
    $WithdrawalBody = @{
        telegram_id = 693173957
        amount = 2.0
        address = "0xdeadbeef"
    } | ConvertTo-Json

    $WithdrawalResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/withdrawals" -Method POST -Body $WithdrawalBody -ContentType "application/json" -UseBasicParsing
    $WithdrawalData = $WithdrawalResponse.Content | ConvertFrom-Json
    $WithdrawalData | ConvertTo-Json | Out-File -FilePath "$ART\withdrawal_req.json" -Encoding UTF8
    $WID = $WithdrawalData.id

    $ApproveResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/admin/withdrawals/$WID/approve" -Method POST -Body "{}" -ContentType "application/json" -Headers @{"Authorization" = "Bearer $TOKEN"} -UseBasicParsing
    $ApproveResponse.Content | Out-File -FilePath "$ART\withdrawal_approve.json" -Encoding UTF8
    Log "Withdrawal created and approved"
} catch {
    Log "ERROR: Withdrawal process failed - $_"
}

Log "9) Collect logs"
try {
    $HealthResponse = Invoke-WebRequest -Uri "$HttpUrl/api/v1/health" -UseBasicParsing
    $HealthResponse.Content | Out-File -FilePath "$ART\health.json" -Encoding UTF8
} catch {
    Log "WARNING: Could not collect final health check"
}

try {
    docker-compose -f docker-compose.staging.yml logs --no-color | Out-File -FilePath "$ART\docker_logs.txt" -Encoding UTF8
} catch {
    Log "WARNING: Could not collect Docker logs"
}

# Create archive
try {
    Compress-Archive -Path $ART -DestinationPath "$ART.zip" -Force
    Log "Archive created: $ART.zip"
} catch {
    Log "WARNING: Could not create archive"
}

$ART | Out-File -FilePath "$ART\ARTIFACT_DIR_PATH.txt" -Encoding UTF8
Log "Done. Artifacts saved in $ART"
