# Pre-release pipeline for CricAlgo
# PowerShell version adapted from bash script

$ErrorActionPreference = "Stop"

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

Log "Preflight checks"

# Check for required commands
try {
    python --version | Out-Null
    Log "Python found"
} catch {
    Log "python not found"; exit 1
}

try {
    git --version | Out-Null
    Log "Git found"
} catch {
    Log "git not found"; exit 1
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

Log "Environment snapshots"
$metadata = @"
TS=$TS
HAS_NPM=$HAS_NPM
HAS_CYPRESS=$HAS_CYPRESS
OS=$([System.Environment]::OSVersion.VersionString)
"@
Set-Content -Path "$ARTDIR/metadata.txt" -Value $metadata

try {
    python --version | Add-Content -Path "$ARTDIR/metadata.txt"
} catch {}

###########################
# 0) Seed admin for tests
###########################
Log "Seeding admin user (for tests) - best effort"
if (Test-Path "app/scripts/seed_admin_static.py") {
    try {
        python app/scripts/seed_admin_static.py 2>&1 | Tee-Object -FilePath "$ARTDIR/seed_admin.log"
        Log "Admin seeding completed"
    } catch {
        Log "seed_admin script may have failed; check $ARTDIR/seed_admin.log"
    }
} else {
    Log "No seed_admin_static.py found; skipping"
}

###########################
# 1) Python deps & lint/typecheck
###########################
Log "Installing python deps (best-effort)"
try {
    python -m pip install -r requirements.txt 2>&1 | Out-Null
    Log "Python dependencies installed"
} catch {
    Log "pip install failed"
}

Log "Running flake8"
try {
    python -m pip install flake8 2>&1 | Out-Null
} catch {}

try {
    flake8 app tests 2>&1 | Set-Content -Path "$ARTDIR/flake8.txt"
    if ((Get-Item "$ARTDIR/flake8.txt").Length -gt 0) {
        Log "flake8 reported issues; saved to $ARTDIR/flake8.txt"
    } else {
        Log "flake8: no issues"
    }
} catch {
    Log "flake8 failed to run"
}

Log "Running mypy"
try {
    python -m pip install mypy 2>&1 | Out-Null
} catch {}

try {
    mypy app 2>&1 | Set-Content -Path "$ARTDIR/mypy.txt"
    if ((Get-Item "$ARTDIR/mypy.txt").Length -gt 0) {
        Log "mypy reported issues; saved to $ARTDIR/mypy.txt"
    } else {
        Log "mypy: no issues"
    }
} catch {
    Log "mypy failed to run"
}

###########################
# 2) Run pytest (unit + integration)
###########################
Log "Running pytest (unit + integration)"
try {
    python -m pip install pytest pytest-asyncio 2>&1 | Out-Null
} catch {}

try {
    pytest -q --maxfail=1 --disable-warnings 2>&1 | Tee-Object -FilePath "$ARTDIR/pytest_full.log"
    $PY_EXIT = $LASTEXITCODE
    if ($PY_EXIT -ne 0) {
        Log "pytest had failures (exit $PY_EXIT) — see $ARTDIR/pytest_full.log"
    } else {
        Log "pytest succeeded"
    }
} catch {
    Log "pytest failed to run"
    $PY_EXIT = 1
}

###########################
# 3) Frontend build (admin UI)
###########################
if ($HAS_NPM -eq 1) {
    Log "Building admin frontend (web/admin)"
    if (Test-Path "web/admin") {
        try {
            Set-Location "web/admin"
            npm ci --silent 2>&1 | Set-Content -Path "../../$ARTDIR/npm_install.log"
            npm run build --silent 2>&1 | Set-Content -Path "../../$ARTDIR/npm_build.log"
            Set-Location "../.."
            
            if ((Get-Item "$ARTDIR/npm_build.log").Length -gt 0) {
                Log "npm build log saved to $ARTDIR/npm_build.log"
            } else {
                Log "npm build completed successfully"
            }
        } catch {
            Log "npm build failed; see $ARTDIR/npm_build.log"
        }
    } else {
        Log "web/admin not found; skipping frontend build"
    }
} else {
    Log "npm not available, skipping frontend build (artifacts still generated)"
}

###########################
# 4) Cypress E2E (headless smoke)
###########################
if ($HAS_CYPRESS -eq 1 -and (Test-Path "tests/e2e")) {
    Log "Running Cypress headless E2E (smoke)"
    try {
        npx cypress run --spec "tests/e2e/**" 2>&1 | Set-Content -Path "$ARTDIR/cypress_run.log"
        Log "Cypress run completed"
    } catch {
        Log "Cypress run had issues; see $ARTDIR/cypress_run.log"
    }
} else {
    Log "Cypress not available or no tests/e2e; creating cypress placeholder"
    $cypressNote = "Cypress not run: HAS_CYPRESS=$HAS_CYPRESS; tests/e2e exists: $((Test-Path 'tests/e2e'))"
    Set-Content -Path "$ARTDIR/cypress_note.txt" -Value $cypressNote
}

###########################
# 5) k6 quick webhook light load (if installed)
###########################
try {
    k6 --version | Out-Null
    if (Test-Path "load/k6/webhook_test.js") {
        Log 'Running short k6 smoke (20 VUs x 15s)'
        try {
            k6 run --vus 20 --duration 15s load/k6/webhook_test.js 2>&1 | Set-Content -Path "$ARTDIR/k6_smoke.log"
            Log "k6 run completed"
        } catch {
            Log "k6 run had issues; see $ARTDIR/k6_smoke.log"
        }
    } else {
        Log "k6 webhook test file not found"
    }
} catch {
    Log "k6 not available; skipping load test"
}

###########################
# 6) Run one-off DB backup validation (dry-run unless explicit)
###########################
$BACKUP_RUN = $env:RUN_BACKUP
if (-not $BACKUP_RUN) { $BACKUP_RUN = "false" }
Log "Backup validation; RUN_BACKUP=$BACKUP_RUN"

if ($BACKUP_RUN -eq "true") {
    if (Test-Path "deploy/on_laptop/db_backup.sh") {
        Log "Executing backup script (this will write to BACKUP_DIR or /var/backups/cricalgo)"
        $BACKUP_DIR = $env:BACKUP_DIR
        if (-not $BACKUP_DIR) { $BACKUP_DIR = "/tmp/cricalgo_backups" }
        New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
        $env:BACKUP_DIR = $BACKUP_DIR
        Copy-Item "deploy/on_laptop/db_backup.sh" "$BACKUP_DIR/db_backup_copy.sh"
        try {
            & "$BACKUP_DIR/db_backup_copy.sh" 2>&1 | Set-Content -Path "$ARTDIR/backup_run.log"
            Log "Backup run completed; see $ARTDIR/backup_run.log"
        } catch {
            Log "backup run failed; see $ARTDIR/backup_run.log"
        }
    } else {
        Log "No db_backup.sh present; skipping"
    }
} else {
    Log "RUN_BACKUP not set to true; skipping real backup (safe default). To run, set RUN_BACKUP=true"
}

###########################
# 7) Collect logs, create summary
###########################
Log "Collecting logs and creating summary"

$summary = @"
Pre-release run summary - $TS
flake8: $(if ((Get-Item "$ARTDIR/flake8.txt" -ErrorAction SilentlyContinue).Length -gt 0) { "issues" } else { "clean" })
mypy:  $(if ((Get-Item "$ARTDIR/mypy.txt" -ErrorAction SilentlyContinue).Length -gt 0) { "issues" } else { "clean" })
pytest: $(if (Test-Path "$ARTDIR/pytest_full.log") { (Get-Content "$ARTDIR/pytest_full.log" | Select-Object -Last 5) -join "`n" } else { "no pytest log" })
npm build: $(if ((Get-Item "$ARTDIR/npm_build.log" -ErrorAction SilentlyContinue).Length -gt 0) { (Get-Content "$ARTDIR/npm_build.log" | Select-Object -Last 5) -join "`n" } else { "skipped or succeeded" })
cypress: $(if (Test-Path "$ARTDIR/cypress_run.log") { (Get-Content "$ARTDIR/cypress_run.log" | Select-Object -Last 5) -join "`n" } else { "skipped" })
k6: $(if (Test-Path "$ARTDIR/k6_smoke.log") { (Get-Content "$ARTDIR/k6_smoke.log" | Select-Object -Last 5) -join "`n" } else { "skipped" })
"@

# Count failures
$FAILURES = 0
if ((Get-Item "$ARTDIR/flake8.txt" -ErrorAction SilentlyContinue).Length -gt 0) { $FAILURES++ }
if ((Get-Item "$ARTDIR/mypy.txt" -ErrorAction SilentlyContinue).Length -gt 0) { $FAILURES++ }
if (Test-Path "$ARTDIR/pytest_full.log") {
    if ((Get-Content "$ARTDIR/pytest_full.log" | Select-String "FAILED").Count -gt 0) { $FAILURES++ }
}
if ((Get-Item "$ARTDIR/npm_build.log" -ErrorAction SilentlyContinue).Length -gt 0) { $FAILURES++ }

$summary += "`nFAILURES=$FAILURES"
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

Set-Content -Path "$ARTDIR/ARTIFACT_DIR_PATH.txt" -Value $ARTDIR
Log "Done. Upload or download $ARTDIR.zip for the full run artifacts."