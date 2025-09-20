# CricAlgo Smoke Test - PowerShell Version
param(
    [string]$StagingHost = "http://localhost:8000",
    [string]$ArtifactDir = "artifacts/smoke_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
)

# Create artifact directory
New-Item -ItemType Directory -Path $ArtifactDir -Force | Out-Null

Write-Host "=== CricAlgo Smoke Test ===" -ForegroundColor Green
Write-Host "Target: $StagingHost" -ForegroundColor Yellow
Write-Host "Artifacts: $ArtifactDir" -ForegroundColor Yellow
Write-Host ""

# Function to log with timestamp
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "[$timestamp] $Message" -ForegroundColor Cyan
}

# Function to check HTTP response
function Test-HttpEndpoint {
    param(
        [string]$Url,
        [int]$ExpectedStatus,
        [string]$Description,
        [string]$OutputFile,
        [hashtable]$Headers = @{},
        [string]$Method = "GET",
        [string]$Body = $null
    )
    
    Write-Log "Testing: $Description"
    
    try {
        $params = @{
            Uri = $Url
            Method = $Method
            Headers = $Headers
            OutFile = $OutputFile
            StatusCodeVariable = "StatusCode"
            ErrorAction = "Stop"
        }
        
        if ($Body) {
            $params.Body = $Body
        }
        
        Invoke-WebRequest @params | Out-Null
        
        if ($StatusCode -eq $ExpectedStatus) {
            Write-Log "✓ $Description - Status: $StatusCode" -ForegroundColor Green
            return $true
        } else {
            Write-Log "✗ $Description - Expected: $ExpectedStatus, Got: $StatusCode" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Log "✗ $Description - Request failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Test 1: Health check
Write-Log "1) Testing health endpoint"
$healthSuccess = Test-HttpEndpoint -Url "$StagingHost/api/v1/health" -ExpectedStatus 200 -Description "Health check" -OutputFile "$ArtifactDir/health.json"

if (-not $healthSuccess) {
    Write-Log "Health check failed - aborting smoke test" -ForegroundColor Red
    exit 2
}

# Display health response
if (Test-Path "$ArtifactDir/health.json") {
    Write-Log "Health response:"
    Get-Content "$ArtifactDir/health.json" | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

# Test 2: Create test user (if API supports it)
Write-Log ""
Write-Log "2) Testing user registration (if supported)"
$registerBody = @{
    telegram_id = 999999999
    username = "smoke_test_user"
} | ConvertTo-Json

$registerHeaders = @{
    "Content-Type" = "application/json"
}

$registerSuccess = Test-HttpEndpoint -Url "$StagingHost/api/v1/auth/register" -ExpectedStatus 200 -Description "User registration" -OutputFile "$ArtifactDir/register_resp.json" -Headers $registerHeaders -Method "POST" -Body $registerBody

if ($registerSuccess) {
    Write-Log "✓ User registration endpoint accessible" -ForegroundColor Green
} else {
    Write-Log "⚠ User registration not available or failed (this may be expected)" -ForegroundColor Yellow
}

# Test 3: Send webhook
Write-Log ""
Write-Log "3) Testing webhook endpoint"
$webhookPayload = @{
    tx_hash = "smoke-$(Get-Date -Format 'yyyyMMddHHmmss')"
    amount = "0.001"
    metadata = @{
        note = "smoke_test"
    }
} | ConvertTo-Json

$webhookHeaders = @{
    "Content-Type" = "application/json"
}

$webhookSuccess = Test-HttpEndpoint -Url "$StagingHost/api/v1/webhooks/bep20" -ExpectedStatus 202 -Description "Webhook submission" -OutputFile "$ArtifactDir/webhook_resp.json" -Headers $webhookHeaders -Method "POST" -Body $webhookPayload

if ($webhookSuccess) {
    Write-Log "✓ Webhook submitted successfully" -ForegroundColor Green
    
    # Display webhook response
    if (Test-Path "$ArtifactDir/webhook_resp.json") {
        Write-Log "Webhook response:"
        Get-Content "$ArtifactDir/webhook_resp.json" | ConvertFrom-Json | ConvertTo-Json -Depth 10
    }
} else {
    Write-Log "✗ Webhook submission failed" -ForegroundColor Red
    exit 3
}

# Test 4: Wait and check for processing
Write-Log ""
Write-Log "4) Waiting 10s for deposit processing..."
Start-Sleep -Seconds 10

# Test 5: Check if we can query transactions (if endpoint exists)
Write-Log ""
Write-Log "5) Testing transaction query (if available)"
$transactionSuccess = Test-HttpEndpoint -Url "$StagingHost/api/v1/transactions" -ExpectedStatus 200 -Description "Transaction query" -OutputFile "$ArtifactDir/transactions.json"

if ($transactionSuccess) {
    Write-Log "✓ Transaction endpoint accessible" -ForegroundColor Green
    if (Test-Path "$ArtifactDir/transactions.json") {
        $transactions = Get-Content "$ArtifactDir/transactions.json" | ConvertFrom-Json
        Write-Log "Transaction count: $($transactions.Count)"
    }
} else {
    Write-Log "⚠ Transaction endpoint not available (this may be expected)" -ForegroundColor Yellow
}

# Test 6: Check system metrics (if available)
Write-Log ""
Write-Log "6) Testing metrics endpoint (if available)"
$metricsSuccess = Test-HttpEndpoint -Url "$StagingHost/metrics" -ExpectedStatus 200 -Description "Metrics endpoint" -OutputFile "$ArtifactDir/metrics.txt"

if ($metricsSuccess) {
    Write-Log "✓ Metrics endpoint accessible" -ForegroundColor Green
    if (Test-Path "$ArtifactDir/metrics.txt") {
        $metrics = Get-Content "$ArtifactDir/metrics.txt"
        $httpRequests = ($metrics | Select-String "http_requests_total").Count
        $celeryTasks = ($metrics | Select-String "celery_task").Count
        Write-Log "Metrics: HTTP requests=$httpRequests, Celery tasks=$celeryTasks"
    }
} else {
    Write-Log "⚠ Metrics endpoint not available" -ForegroundColor Yellow
}

# Summary
Write-Log ""
Write-Log "=== Smoke Test Summary ===" -ForegroundColor Green
Write-Log "✓ Health check passed" -ForegroundColor Green
Write-Log "✓ Webhook submission passed" -ForegroundColor Green
Write-Log "⚠ User registration: $(if ($registerSuccess) { 'available' } else { 'not available' })" -ForegroundColor Yellow
Write-Log "⚠ Transaction query: $(if ($transactionSuccess) { 'available' } else { 'not available' })" -ForegroundColor Yellow
Write-Log "⚠ Metrics: $(if ($metricsSuccess) { 'available' } else { 'not available' })" -ForegroundColor Yellow

Write-Log ""
Write-Log "Artifacts saved to: $ArtifactDir" -ForegroundColor Yellow
Write-Log "Smoke test completed successfully!" -ForegroundColor Green

# List artifacts
Write-Log ""
Write-Log "Generated artifacts:"
Get-ChildItem $ArtifactDir | ForEach-Object {
    Write-Log "  $($_.Name) ($($_.Length) bytes)"
}
