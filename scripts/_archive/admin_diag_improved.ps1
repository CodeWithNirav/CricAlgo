# Improved Admin Diagnostic Script (PowerShell)
# Tests all admin endpoints and provides detailed error reporting

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$AdminUser = "admin",
    [string]$AdminPass = "admin123"
)

# Configuration
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputDir = "artifacts\admin_diag_$Timestamp"
$LogFile = "$OutputDir\diagnostic.log"

# Create output directory
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# Logging function
function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Write-Host $logMessage -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $logMessage
}

Write-Log "=== CricAlgo Admin Diagnostic - $(Get-Date) ===" "Green"

# Test 1: Health check
Write-Log "`n1. Testing health endpoint..." "Yellow"
try {
    $healthResponse = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 10
    Write-Log "✓ Health endpoint responding" "Green"
} catch {
    Write-Log "✗ Health endpoint failed: $($_.Exception.Message)" "Red"
}

# Test 2: Admin login
Write-Log "`n2. Testing admin login..." "Yellow"
try {
    $loginBody = @{
        username = $AdminUser
        password = $AdminPass
    } | ConvertTo-Json

    $loginResponse = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/admin/login" -Method Post -Body $loginBody -ContentType "application/json" -TimeoutSec 10
    
    if ($loginResponse.access_token) {
        $adminToken = $loginResponse.access_token
        Write-Log "✓ Admin login successful" "Green"
        $adminToken | Out-File -FilePath "$OutputDir\admin_token.txt" -Encoding UTF8
    } else {
        Write-Log "✗ Admin login response invalid: $($loginResponse | ConvertTo-Json)" "Red"
        $adminToken = $null
    }
} catch {
    Write-Log "✗ Admin login failed: $($_.Exception.Message)" "Red"
    $adminToken = $null
}

# Test 3: Admin endpoints (if token available)
if ($adminToken) {
    $authHeader = @{ "Authorization" = "Bearer $adminToken" }
    
    # Test invite codes endpoint (canonical)
    Write-Log "`n3. Testing invite codes endpoint (canonical)..." "Yellow"
    try {
        $inviteResponse = Invoke-RestMethod -Uri "$BaseUrl/api/v1/admin/invite_codes" -Method Get -Headers $authHeader -TimeoutSec 10
        Write-Log "✓ Invite codes endpoint working" "Green"
        $inviteResponse | ConvertTo-Json -Depth 10 | Out-File -FilePath "$OutputDir\invite_codes.json" -Encoding UTF8
    } catch {
        Write-Log "✗ Invite codes endpoint failed: $($_.Exception.Message)" "Red"
        $_.Exception.Message | Out-File -FilePath "$OutputDir\invite_codes_error.txt" -Encoding UTF8
    }
    
    # Test invite codes endpoint (alias)
    Write-Log "`n4. Testing invite codes endpoint (alias)..." "Yellow"
    try {
        $inviteAliasResponse = Invoke-RestMethod -Uri "$BaseUrl/api/v1/admin/invitecodes" -Method Get -Headers $authHeader -TimeoutSec 10
        Write-Log "✓ Invite codes alias endpoint working" "Green"
    } catch {
        Write-Log "✗ Invite codes alias endpoint failed: $($_.Exception.Message)" "Red"
        $_.Exception.Message | Out-File -FilePath "$OutputDir\invite_codes_alias_error.txt" -Encoding UTF8
    }
    
    # Test users endpoint
    Write-Log "`n5. Testing users endpoint..." "Yellow"
    try {
        $usersResponse = Invoke-RestMethod -Uri "$BaseUrl/api/v1/admin/users?limit=10" -Method Get -Headers $authHeader -TimeoutSec 10
        Write-Log "✓ Users endpoint working" "Green"
        $usersResponse | ConvertTo-Json -Depth 10 | Out-File -FilePath "$OutputDir\users.json" -Encoding UTF8
    } catch {
        Write-Log "✗ Users endpoint failed: $($_.Exception.Message)" "Red"
        $_.Exception.Message | Out-File -FilePath "$OutputDir\users_error.txt" -Encoding UTF8
    }
    
    # Test admin UI static files
    Write-Log "`n6. Testing admin UI static files..." "Yellow"
    try {
        $staticResponse = Invoke-WebRequest -Uri "$BaseUrl/static/admin/index.html" -Method Get -TimeoutSec 10
        if ($staticResponse.StatusCode -eq 200) {
            Write-Log "✓ Admin UI static files accessible" "Green"
        } else {
            Write-Log "✗ Admin UI static files not accessible (Status: $($staticResponse.StatusCode))" "Red"
        }
    } catch {
        Write-Log "✗ Admin UI static files not accessible: $($_.Exception.Message)" "Red"
    }
    
} else {
    Write-Log "✗ Skipping admin endpoint tests - no valid token" "Red"
}

# Test 7: Database connectivity (if possible)
Write-Log "`n7. Testing database connectivity..." "Yellow"
if (Get-Command psql -ErrorAction SilentlyContinue) {
    try {
        $dbUrl = $env:DATABASE_URL
        if (-not $dbUrl) {
            $dbUrl = "postgresql://postgres:postgres@localhost:5432/cricalgo"
        }
        
        $dbTest = psql $dbUrl -c "SELECT 1;" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Log "✓ Database connection successful" "Green"
            
            # Check if invitation_codes table exists
            $tableExists = psql $dbUrl -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'invitation_codes');" 2>$null
            if ($tableExists.Trim() -eq "t") {
                Write-Log "✓ invitation_codes table exists" "Green"
                
                # Count records
                $recordCount = psql $dbUrl -t -c "SELECT COUNT(*) FROM invitation_codes;" 2>$null
                Write-Log "  - Records in invitation_codes: $($recordCount.Trim())"
            } else {
                Write-Log "✗ invitation_codes table does not exist" "Red"
            }
        } else {
            Write-Log "✗ Database connection failed" "Red"
        }
    } catch {
        Write-Log "✗ Database test failed: $($_.Exception.Message)" "Red"
    }
} else {
    Write-Log "⚠ psql not available, skipping database tests" "Yellow"
}

# Generate summary
Write-Log "`n=== DIAGNOSTIC SUMMARY ===" "Yellow"
Write-Log "Output directory: $OutputDir"
Write-Log "Log file: $LogFile"

# Create zip file
try {
    Compress-Archive -Path "$OutputDir\*" -DestinationPath "artifacts\admin_diag_$Timestamp.zip" -Force
    Write-Log "`n✓ Diagnostic complete. Results saved to: artifacts\admin_diag_$Timestamp.zip" "Green"
    Write-Log "`nTo view results:"
    Write-Log "  Expand-Archive -Path artifacts\admin_diag_$Timestamp.zip -DestinationPath temp_diag"
} catch {
    Write-Log "✗ Failed to create zip file: $($_.Exception.Message)" "Red"
}
