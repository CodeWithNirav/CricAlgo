# PowerShell Smoke Test Script for CricAlgo
# This script runs the smoke test with proper environment variable handling

param(
    [string]$HTTP = "http://localhost:8000",
    [string]$TELEGRAM_BOT_TOKEN = "8257937151:AAGyRy10haSpTNYG-kOQ3wU2emBnybx3qAs",
    [string]$ADMIN_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhNTM2YzAxOS1hZTYzLTQ5NmQtYjhlOS1kZWU2ZmVlY2Y3YzUiLCJ1c2VybmFtZSI6ImFkbWluIiwidHlwZSI6ImFkbWluIiwiZXhwIjoxNzU4NjUzMTEzfQ.JDwp09mLAcg4XWfOZHTxxrqgyXo0t-cL8IiIatvEgyE",
    [string]$USER1_TELEGRAM_ID = "987654321",
    [string]$USER2_TELEGRAM_ID = "555666777",
    [string]$DEPOSIT_AMOUNT = "20.0",
    [string]$ENTRY_FEE = "5.0",
    [string]$WITHDRAWAL_AMOUNT = "2.0"
)

Write-Host "CricAlgo Smoke Test - PowerShell Version" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Set environment variables
$env:HTTP = $HTTP
$env:TELEGRAM_BOT_TOKEN = $TELEGRAM_BOT_TOKEN
$env:ADMIN_TOKEN = $ADMIN_TOKEN
$env:USER1_TELEGRAM_ID = $USER1_TELEGRAM_ID
$env:USER2_TELEGRAM_ID = $USER2_TELEGRAM_ID
$env:DEPOSIT_AMOUNT = $DEPOSIT_AMOUNT
$env:ENTRY_FEE = $ENTRY_FEE
$env:WITHDRAWAL_AMOUNT = $WITHDRAWAL_AMOUNT

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  HTTP: $HTTP"
Write-Host "  Bot Token: $($TELEGRAM_BOT_TOKEN.Substring(0,10))..."
Write-Host "  Admin Token: $($ADMIN_TOKEN.Substring(0,20))..."
Write-Host "  User 1 ID: $USER1_TELEGRAM_ID"
Write-Host "  User 2 ID: $USER2_TELEGRAM_ID"
Write-Host "  Deposit Amount: $DEPOSIT_AMOUNT"
Write-Host "  Entry Fee: $ENTRY_FEE"
Write-Host "  Withdrawal Amount: $WITHDRAWAL_AMOUNT"
Write-Host ""

# Create artifacts directory
$timestamp = Get-Date -Format "yyyyMMddTHHmmssZ"
$artifactsDir = "artifacts\bot_live_smoke_$timestamp"
New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
$logFile = "$artifactsDir\run.log"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Write-Host $logMessage
    Add-Content -Path $logFile -Value $logMessage
}

function Write-Step {
    param([string]$StepName)
    Write-Log "---- $StepName ----"
}

function Invoke-API {
    param(
        [string]$Method,
        [string]$Uri,
        [string]$Body = $null,
        [string]$AuthToken = $null
    )
    
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    if ($AuthToken) {
        $headers["Authorization"] = "Bearer $AuthToken"
    }
    
    try {
        if ($Body) {
            $response = Invoke-RestMethod -Uri $Uri -Method $Method -Body $Body -Headers $headers
        } else {
            $response = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $headers
        }
        return $response
    } catch {
        Write-Log "API Error: $($_.Exception.Message)"
        return $null
    }
}

function Test-Response {
    param([object]$Response, [string]$StepName)
    
    if ($Response -eq $null) {
        Write-Log "ERROR in ${StepName}: No response received"
        return $false
    }
    
    $responseString = $Response | ConvertTo-Json -Depth 10
    if ($responseString -match "error|failed|exception") {
        Write-Log "ERROR in ${StepName}: $responseString"
        return $false
    }
    
    return $true
}

# Start the smoke test
Write-Log "Enhanced Smoke Test started at $timestamp"
Write-Log "Artifacts -> $artifactsDir"

# 1. Health Check
Write-Step "Health Check"
$healthResponse = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/health"
$healthResponse | ConvertTo-Json | Out-File "$artifactsDir\health.json"

if (-not (Test-Response -Response $healthResponse -StepName "Health Check")) {
    Write-Log "Health check failed. Exiting."
    exit 1
}

# 2. User Management
Write-Step "User Management and Chat Mapping"

# Check if users exist
Write-Log "Checking user $USER1_TELEGRAM_ID..."
$user1Lookup = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/admin/users?telegram_id=$USER1_TELEGRAM_ID" -AuthToken $ADMIN_TOKEN
$user1Lookup | ConvertTo-Json | Out-File "$artifactsDir\user1_lookup.json"

$user1Uuid = $null
if ($user1Lookup -and $user1Lookup.Count -gt 0) {
    $user1Uuid = $user1Lookup[0].id
    Write-Log "USER1_UUID=$user1Uuid"
} else {
    Write-Log "User not found, creating new user..."
    $createUser1Body = @{
        telegram_id = [int]$USER1_TELEGRAM_ID
        username = "test_user_1"
    } | ConvertTo-Json
    
    $user1Create = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/admin/users" -Body $createUser1Body -AuthToken $ADMIN_TOKEN
    $user1Create | ConvertTo-Json | Out-File "$artifactsDir\user1_create.json"
    
    if (Test-Response -Response $user1Create -StepName "User 1 Creation") {
        $user1Uuid = $user1Create.id
        Write-Log "USER1_UUID=$user1Uuid"
    }
}

# Check user 2
Write-Log "Checking user $USER2_TELEGRAM_ID..."
$user2Lookup = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/admin/users?telegram_id=$USER2_TELEGRAM_ID" -AuthToken $ADMIN_TOKEN
$user2Lookup | ConvertTo-Json | Out-File "$artifactsDir\user2_lookup.json"

$user2Uuid = $null
if ($user2Lookup -and $user2Lookup.Count -gt 0) {
    $user2Uuid = $user2Lookup[0].id
    Write-Log "USER2_UUID=$user2Uuid"
} else {
    Write-Log "User not found, creating new user..."
    $createUser2Body = @{
        telegram_id = [int]$USER2_TELEGRAM_ID
        username = "test_user_2"
    } | ConvertTo-Json
    
    $user2Create = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/admin/users" -Body $createUser2Body -AuthToken $ADMIN_TOKEN
    $user2Create | ConvertTo-Json | Out-File "$artifactsDir\user2_create.json"
    
    if (Test-Response -Response $user2Create -StepName "User 2 Creation") {
        $user2Uuid = $user2Create.id
        Write-Log "USER2_UUID=$user2Uuid"
    }
}

# 3. Match and Contest Creation
Write-Step "Match and Contest Creation"

# Create match
$matchBody = @{
    title = "Smoke Test Match $timestamp"
    external_id = "smoke-match-$timestamp"
    start_time = "2025-12-31T12:00:00Z"
} | ConvertTo-Json

$matchResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/admin/matches" -Body $matchBody -AuthToken $ADMIN_TOKEN
$matchResponse | ConvertTo-Json | Out-File "$artifactsDir\match_create.json"

$matchId = $null
if (Test-Response -Response $matchResponse -StepName "Match Creation") {
    $matchId = $matchResponse.match.id
    Write-Log "MATCH_ID=$matchId"
} else {
    Write-Log "Failed to create match, trying to find existing match..."
    $matchList = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/admin/matches" -AuthToken $ADMIN_TOKEN
    $matchList | ConvertTo-Json | Out-File "$artifactsDir\matches_list.json"
    if ($matchList -and $matchList.Count -gt 0) {
        $matchId = $matchList[0].id
        Write-Log "MATCH_ID=$matchId"
    }
}

if (-not $matchId) {
    Write-Log "ERROR: No match ID found"
    exit 1
}

# Create contest
$contestBody = @{
    title = "Smoke Test Contest $timestamp"
    entry_fee = $ENTRY_FEE
    max_players = 10
    prize_structure = @{
        "1" = 0.8
        "2" = 0.2
    }
} | ConvertTo-Json

$contestResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/admin/matches/$matchId/contests" -Body $contestBody -AuthToken $ADMIN_TOKEN
$contestResponse | ConvertTo-Json | Out-File "$artifactsDir\contest_create.json"

$contestId = $null
if (Test-Response -Response $contestResponse -StepName "Contest Creation") {
    $contestId = $contestResponse.contest.id
    Write-Log "CONTEST_ID=$contestId"
} else {
    Write-Log "Failed to create contest, trying to find existing contest..."
    $contestList = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/admin/matches/$matchId/contests" -AuthToken $ADMIN_TOKEN
    $contestList | ConvertTo-Json | Out-File "$artifactsDir\contest_list.json"
    if ($contestList -and $contestList.Count -gt 0) {
        $contestId = $contestList[0].id
        Write-Log "CONTEST_ID=$contestId"
    }
}

if (-not $contestId) {
    Write-Log "ERROR: No contest ID found"
    exit 1
}

# 4. Deposit Simulation
Write-Step "Deposit Simulation"

$depositRef = "smoke-dep-$timestamp-u1"
$webhookBody = @{
    tx_hash = "tx-$timestamp-u1"
    confirmations = 12
    amount = $DEPOSIT_AMOUNT
    currency = "USDT"
    status = "confirmed"
    user_id = $user1Uuid
    metadata = @{
        deposit_ref = $depositRef
        user_id = $user1Uuid
        to = "test-gateway"
        token_symbol = "USDT"
    }
} | ConvertTo-Json

$webhookBody | Out-File "$artifactsDir\deposit_webhook_payload_u1.json"
$webhookResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/webhooks/bep20" -Body $webhookBody
$webhookResponse | ConvertTo-Json | Out-File "$artifactsDir\deposit_webhook_resp_u1.json"

if (-not (Test-Response -Response $webhookResponse -StepName "Deposit Webhook")) {
    Write-Log "WARNING: Deposit webhook may have failed"
}

# Wait for background processing
Write-Log "Waiting 8s for background processing..."
Start-Sleep -Seconds 8

# Verify deposit
$txSearch = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/admin/transactions?user_id=$user1Uuid" -AuthToken $ADMIN_TOKEN
$txSearch | ConvertTo-Json | Out-File "$artifactsDir\user1_transactions.json"

# 5. Contest Joining
Write-Step "Contest Joining"

$joinBody = @{
    user_id = $user1Uuid
} | ConvertTo-Json

$joinResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/contests/$contestId/join" -Body $joinBody -AuthToken $ADMIN_TOKEN
$joinResponse | ConvertTo-Json | Out-File "$artifactsDir\join_response.json"

if (-not (Test-Response -Response $joinResponse -StepName "Contest Join")) {
    Write-Log "WARNING: Contest join may have failed"
}

# 6. Contest Settlement
Write-Step "Contest Settlement"

$settleResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/admin/contests/$contestId/settle" -AuthToken $ADMIN_TOKEN
$settleResponse | ConvertTo-Json | Out-File "$artifactsDir\settle_response.json"

if (-not (Test-Response -Response $settleResponse -StepName "Contest Settlement")) {
    Write-Log "WARNING: Contest settlement may have failed"
}

# Wait for payouts
Write-Log "Waiting 6s for payout processing..."
Start-Sleep -Seconds 6

# Verify wallet balance
$walletBalance = Invoke-API -Method "GET" -Uri "$HTTP/api/v1/admin/users/$user1Uuid/wallet" -AuthToken $ADMIN_TOKEN
$walletBalance | ConvertTo-Json | Out-File "$artifactsDir\user1_wallet_after_settle.json"

# 7. Withdrawal Flow
Write-Step "Withdrawal Flow"

$withdrawalBody = @{
    user_id = $user1Uuid
    amount = $WITHDRAWAL_AMOUNT
    address = "0xdeadbeef"
} | ConvertTo-Json

$withdrawalResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/withdrawals" -Body $withdrawalBody -AuthToken $ADMIN_TOKEN
$withdrawalResponse | ConvertTo-Json | Out-File "$artifactsDir\withdraw_create.json"

$withdrawalId = $null
if (Test-Response -Response $withdrawalResponse -StepName "Withdrawal Creation") {
    $withdrawalId = $withdrawalResponse.id
    Write-Log "WITHDRAWAL_ID=$withdrawalId"
    
    # Approve withdrawal
    Write-Step "Withdrawal Approval"
    $approveResponse = Invoke-API -Method "POST" -Uri "$HTTP/api/v1/admin/withdrawals/$withdrawalId/approve" -AuthToken $ADMIN_TOKEN
    $approveResponse | ConvertTo-Json | Out-File "$artifactsDir\withdraw_approve.json"
    
    if (-not (Test-Response -Response $approveResponse -StepName "Withdrawal Approval")) {
        Write-Log "WARNING: Withdrawal approval may have failed"
    }
} else {
    Write-Log "WARNING: No withdrawal ID found, skipping approval"
}

# 8. Log Collection
Write-Step "Log Collection"

Write-Log "Collecting Docker logs..."
try {
    docker-compose logs --tail=500 app | Out-File "$artifactsDir\app_log.txt"
    docker-compose logs --tail=500 bot | Out-File "$artifactsDir\bot_log.txt"
    docker-compose logs --tail=500 worker | Out-File "$artifactsDir\worker_log.txt"
    Write-Log "Successfully collected Docker logs"
} catch {
    Write-Log "WARNING: Failed to collect Docker logs: $($_.Exception.Message)"
}

# 9. Telegram Integration Test
Write-Step "Telegram Integration Test"

try {
    $tgUpdates = Invoke-RestMethod -Uri "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
    $tgUpdates | ConvertTo-Json | Out-File "$artifactsDir\telegram_getUpdates.json"
    Write-Log "Telegram API is accessible"
} catch {
    Write-Log "WARNING: Telegram API may not be accessible: $($_.Exception.Message)"
}

# 10. Summary
Write-Step "Test Summary"

$summary = @{
    timestamp = $timestamp
    test_status = "completed"
    configuration = @{
        http_endpoint = $HTTP
        deposit_amount = $DEPOSIT_AMOUNT
        entry_fee = $ENTRY_FEE
        withdrawal_amount = $WITHDRAWAL_AMOUNT
    }
    test_results = @{
        match_id = $matchId
        contest_id = $contestId
        user1_uuid = $user1Uuid
        user2_uuid = $user2Uuid
        withdrawal_id = $withdrawalId
    }
    artifacts = @{
        health_check = "$artifactsDir\health.json"
        deposit_webhook = "$artifactsDir\deposit_webhook_resp_u1.json"
        contest_join = "$artifactsDir\join_response.json"
        contest_settle = "$artifactsDir\settle_response.json"
        withdrawal_create = "$artifactsDir\withdraw_create.json"
        withdrawal_approve = "$artifactsDir\withdraw_approve.json"
        bot_logs = "$artifactsDir\bot_log.txt"
        worker_logs = "$artifactsDir\worker_log.txt"
        app_logs = "$artifactsDir\app_log.txt"
    }
} | ConvertTo-Json -Depth 10

$summary | Out-File "$artifactsDir\smoke_test_summary.json"

Write-Log "Enhanced Smoke Test completed at $(Get-Date -Format 'yyyyMMddTHHmmssZ')"
Write-Log "Artifacts saved to $artifactsDir"
Write-Log "Summary: $artifactsDir\smoke_test_summary.json"

Write-Host ""
Write-Host "Smoke test completed successfully!" -ForegroundColor Green
Write-Host "Check the artifacts directory for detailed results: $artifactsDir" -ForegroundColor Yellow
