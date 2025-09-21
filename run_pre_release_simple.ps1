# Pre-release pipeline for CricAlgo - Simplified PowerShell version

$ErrorActionPreference = "Continue"

# Set environment variables
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/cricalgo"
$env:SEED_ADMIN_USERNAME = "admin"
$env:SEED_ADMIN_PASSWORD = "admin123"
$env:SEED_ADMIN_NO_2FA = "true"

$TS = Get-Date -Format "yyyyMMddTHHmmssZ"
$ARTDIR = "artifacts/pre_release_$TS"
New-Item -ItemType Directory -Path $ARTDIR -Force | Out-Null

function Log {
    param($Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = ">>> $Message"
    Write-Host $logMessage
    Add-Content -Path "$ARTDIR/run.log" -Value "$timestamp $logMessage"
}

Log "Starting pre-release pipeline"

# Check for required commands
try {
    python --version | Out-Null
    Log "Python found"
} catch {
    Log "python not found"
    exit 1
}

try {
    git --version | Out-Null
    Log "Git found"
} catch {
    Log "git not found"
    exit 1
}

# Check for optional commands
$HAS_NPM = 0
try {
    npm --version | Out-Null
    $HAS_NPM = 1
    Log "npm found"
} catch {
    Log "npm not available"
}

$HAS_CYPRESS = 0
try {
    npx cypress --version | Out-Null
    $HAS_CYPRESS = 1
    Log "Cypress found"
} catch {
    Log "Cypress not available"
}

# Save metadata
$metadata = "TS=$TS`nHAS_NPM=$HAS_NPM`nHAS_CYPRESS=$HAS_CYPRESS`nOS=$([System.Environment]::OSVersion.VersionString)"
Set-Content -Path "$ARTDIR/metadata.txt" -Value $metadata

###########################
# 0) Seed admin for tests
###########################
Log "Seeding admin user (for tests)"
if (Test-Path "app/scripts/seed_admin_static.py") {
    try {
        python app/scripts/seed_admin_static.py 2>&1 | Tee-Object -FilePath "$ARTDIR/seed_admin.log"
        Log "Admin seeding completed"
    } catch {
        Log "seed_admin script may have failed"
    }
} else {
    Log "No seed_admin_static.py found; skipping"
}

###########################
# 1) Python deps & lint/typecheck
###########################
Log "Installing python deps"
try {
    python -m pip install -r requirements.txt 2>&1 | Out-Null
    Log "Python dependencies installed"
} catch {
    Log "pip install failed"
}

Log "Running flake8"
try {
    python -m pip install flake8 2>&1 | Out-Null
    flake8 app tests 2>&1 | Set-Content -Path "$ARTDIR/flake8.txt"
    if ((Get-Item "$ARTDIR/flake8.txt").Length -gt 0) {
        Log "flake8 reported issues"
    } else {
        Log "flake8: no issues"
    }
} catch {
    Log "flake8 failed to run"
}

Log "Running mypy"
try {
    python -m pip install mypy 2>&1 | Out-Null
    mypy app 2>&1 | Set-Content -Path "$ARTDIR/mypy.txt"
    if ((Get-Item "$ARTDIR/mypy.txt").Length -gt 0) {
        Log "mypy reported issues"
    } else {
        Log "mypy: no issues"
    }
} catch {
    Log "mypy failed to run"
}

###########################
# 2) Run pytest
###########################
Log "Running pytest"
try {
    python -m pip install pytest pytest-asyncio 2>&1 | Out-Null
    pytest -q --maxfail=1 --disable-warnings 2>&1 | Tee-Object -FilePath "$ARTDIR/pytest_full.log"
    $PY_EXIT = $LASTEXITCODE
    if ($PY_EXIT -ne 0) {
        Log "pytest had failures"
    } else {
        Log "pytest succeeded"
    }
} catch {
    Log "pytest failed to run"
    $PY_EXIT = 1
}

###########################
# 3) Frontend build
###########################
if ($HAS_NPM -eq 1) {
    Log "Building admin frontend"
    if (Test-Path "web/admin") {
        try {
            Set-Location "web/admin"
            npm ci --silent 2>&1 | Set-Content -Path "../../$ARTDIR/npm_install.log"
            npm run build --silent 2>&1 | Set-Content -Path "../../$ARTDIR/npm_build.log"
            Set-Location "../.."
            Log "npm build completed"
        } catch {
            Log "npm build failed"
        }
    } else {
        Log "web/admin not found; skipping frontend build"
    }
} else {
    Log "npm not available, skipping frontend build"
}

###########################
# 4) Cypress E2E
###########################
if ($HAS_CYPRESS -eq 1 -and (Test-Path "tests/e2e")) {
    Log "Running Cypress headless E2E"
    try {
        npx cypress run --spec "tests/e2e/**" 2>&1 | Set-Content -Path "$ARTDIR/cypress_run.log"
        Log "Cypress run completed"
    } catch {
        Log "Cypress run had issues"
    }
} else {
    Log "Cypress not available or no tests/e2e"
    $cypressNote = "Cypress not run: HAS_CYPRESS=$HAS_CYPRESS; tests/e2e exists: $((Test-Path 'tests/e2e'))"
    Set-Content -Path "$ARTDIR/cypress_note.txt" -Value $cypressNote
}

###########################
# 5) k6 load test
###########################
try {
    k6 --version | Out-Null
    if (Test-Path "load/k6/webhook_test.js") {
        Log "Running short k6 smoke test"
        try {
            k6 run --vus 20 --duration 15s load/k6/webhook_test.js 2>&1 | Set-Content -Path "$ARTDIR/k6_smoke.log"
            Log "k6 run completed"
        } catch {
            Log "k6 run had issues"
        }
    } else {
        Log "k6 webhook test file not found"
    }
} catch {
    Log "k6 not available; skipping load test"
}

###########################
# 6) Create summary
###########################
Log "Creating summary"

# Count failures
$FAILURES = 0
if (Test-Path "$ARTDIR/flake8.txt") {
    if ((Get-Item "$ARTDIR/flake8.txt").Length -gt 0) { $FAILURES++ }
}
if (Test-Path "$ARTDIR/mypy.txt") {
    if ((Get-Item "$ARTDIR/mypy.txt").Length -gt 0) { $FAILURES++ }
}
if (Test-Path "$ARTDIR/pytest_full.log") {
    if ((Get-Content "$ARTDIR/pytest_full.log" | Select-String "FAILED").Count -gt 0) { $FAILURES++ }
}
if (Test-Path "$ARTDIR/npm_build.log") {
    if ((Get-Item "$ARTDIR/npm_build.log").Length -gt 0) { $FAILURES++ }
}

$summary = @"
Pre-release run summary - $TS
flake8: $(if (Test-Path "$ARTDIR/flake8.txt" -and (Get-Item "$ARTDIR/flake8.txt").Length -gt 0) { "issues" } else { "clean" })
mypy: $(if (Test-Path "$ARTDIR/mypy.txt" -and (Get-Item "$ARTDIR/mypy.txt").Length -gt 0) { "issues" } else { "clean" })
pytest: $(if (Test-Path "$ARTDIR/pytest_full.log") { "completed" } else { "not run" })
npm build: $(if (Test-Path "$ARTDIR/npm_build.log" -and (Get-Item "$ARTDIR/npm_build.log").Length -gt 0) { "issues" } else { "clean" })
cypress: $(if (Test-Path "$ARTDIR/cypress_run.log") { "completed" } else { "skipped" })
k6: $(if (Test-Path "$ARTDIR/k6_smoke.log") { "completed" } else { "skipped" })
FAILURES=$FAILURES
"@

Set-Content -Path "$ARTDIR/summary.txt" -Value $summary

Log "Pre-release pipeline completed. Artifacts are in $ARTDIR"
Log "Total failures: $FAILURES"

# Create zip archive
try {
    Compress-Archive -Path $ARTDIR -DestinationPath "$ARTDIR.zip" -Force
    Log "Created $ARTDIR.zip"
} catch {
    Log "Failed to create zip archive"
}

Log "Done. Check $ARTDIR for results."
