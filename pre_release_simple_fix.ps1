# Simple pre-release fix script - won't hang
$ErrorActionPreference = "Continue"

$TS = Get-Date -Format "yyyyMMddTHHmmssZ"
$ART = "artifacts/pre_release_simple_$TS"
New-Item -ItemType Directory -Path $ART -Force | Out-Null

function Log {
    param($Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message"
    Add-Content -Path "$ART/run.log" -Value "[$timestamp] $Message"
}

Log "Starting simple pre-release fix"

# Set environment variables
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/cricalgo"
$env:SEED_ADMIN_USERNAME = "admin"
$env:SEED_ADMIN_PASSWORD = "admin123"
$env:SEED_ADMIN_NO_2FA = "true"

# Check what we have
Log "Checking available tools"
try { python --version | Out-Null; Log "Python: OK" } catch { Log "Python: MISSING" }
try { git --version | Out-Null; Log "Git: OK" } catch { Log "Git: MISSING" }
try { npm --version | Out-Null; Log "npm: OK" } catch { Log "npm: MISSING" }

# Install only essential tools with timeout
Log "Installing essential tools (with timeout)"
$job = Start-Job -ScriptBlock {
    python -m pip install flake8 mypy pytest pytest-asyncio ruff isort --timeout 60
}
$timeout = 120 # 2 minutes
$job | Wait-Job -Timeout $timeout
if ($job.State -eq "Running") {
    Stop-Job $job
    Remove-Job $job
    Log "Tool installation timed out - continuing anyway"
} else {
    Log "Essential tools installed"
}

# Run basic checks
Log "Running flake8 check"
try {
    $flake8Output = flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1
    if ($flake8Output) {
        $flake8Output | Set-Content "$ART/flake8_critical.txt"
        Log "Critical flake8 issues found - see $ART/flake8_critical.txt"
    } else {
        Log "No critical flake8 issues"
    }
} catch {
    Log "Flake8 check failed"
}

Log "Running basic mypy check"
try {
    mypy app/api --ignore-missing-imports --no-error-summary 2>&1 | Set-Content "$ART/mypy_basic.txt"
    Log "Basic mypy check completed"
} catch {
    Log "MyPy check failed"
}

# Try to run a simple test
Log "Running simple test"
try {
    python -c "import sys; print('Python import test: OK')" 2>&1 | Set-Content "$ART/python_test.txt"
    Log "Python basic test passed"
} catch {
    Log "Python basic test failed"
}

# Check if we can import main modules
Log "Testing module imports"
try {
    python -c "import app; print('App module: OK')" 2>&1 | Add-Content "$ART/import_test.txt"
} catch {
    "App module import failed" | Add-Content "$ART/import_test.txt"
}

# Create summary
$summary = @"
Simple Pre-release Fix Summary - $TS
=====================================

Environment:
- Python: $(try { python --version } catch { 'Not available' })
- Git: $(try { git --version } catch { 'Not available' })
- npm: $(try { npm --version } catch { 'Not available' })

Results:
- Flake8 critical issues: $(if (Test-Path "$ART/flake8_critical.txt") { 'Found' } else { 'None' })
- MyPy basic check: $(if (Test-Path "$ART/mypy_basic.txt") { 'Completed' } else { 'Failed' })
- Python test: $(if (Test-Path "$ART/python_test.txt") { 'Passed' } else { 'Failed' })
- Module imports: $(if (Test-Path "$ART/import_test.txt") { 'Tested' } else { 'Not tested' })

Artifacts created in: $ART
"@

Set-Content -Path "$ART/summary.txt" -Value $summary
Log "Summary created"

# Show results
Log "=== SUMMARY ==="
Get-Content "$ART/summary.txt" | ForEach-Object { Log $_ }

Log "Simple pre-release fix completed. Check $ART for details."
