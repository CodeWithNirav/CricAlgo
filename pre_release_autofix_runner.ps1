# Pre-release autofix pipeline for CricAlgo
# PowerShell version

$ErrorActionPreference = "Continue"

$TS = Get-Date -Format "yyyyMMddTHHmmssZ"
$ART = "artifacts/pre_release_autofix_$TS"
New-Item -ItemType Directory -Path $ART -Force | Out-Null

function Log {
    param($Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = ">>> $Message"
    Write-Host $logMessage
    Add-Content -Path "$ART/run.log" -Value "$timestamp $logMessage"
}

Log "Starting pre-release autofix pipeline"

Log "Create venv and activate"
try {
    python -m venv .venv
    Log "Virtual environment created"
} catch {
    Log "Virtual environment creation failed or already exists"
}

# Activate virtual environment
if (Test-Path ".venv/Scripts/Activate.ps1") {
    . .venv/Scripts/Activate.ps1
    Log "Virtual environment activated"
} else {
    Log "Could not activate virtual environment"
}

Log "Prepare requirements_no_k6.txt"
if (-not (Test-Path "requirements_no_k6.txt")) {
    if (Test-Path "requirements.txt") {
        Get-Content "requirements.txt" | Where-Object { $_ -notmatch "k6" } | Set-Content "requirements_no_k6.txt"
        Log "Created requirements_no_k6.txt"
    } else {
        "requirements.txt missing" | Set-Content "$ART/err.txt"
        Log "ERROR: requirements.txt missing"
        exit 1
    }
}

Log "Install core deps"
try {
    python -m pip install --upgrade pip
    Log "pip upgraded"
} catch {
    Log "pip upgrade failed"
}

try {
    python -m pip install -r requirements_no_k6.txt
    Log "Core dependencies installed"
} catch {
    Log "pip install failed; saving pip log"
    python -m pip freeze | Set-Content "$ART/pip_freeze.txt"
}

Log "Install lint & formatting tools"
try {
    python -m pip install ruff isort flake8 mypy pytest pytest-asyncio 2>&1 | Out-Null
    Log "Lint and formatting tools installed"
} catch {
    Log "Some lint tools installation failed"
}

Log "Auto-format & fix with ruff"
try {
    ruff format . 2>&1 | Out-Null
    Log "Ruff formatting completed"
} catch {
    Log "Ruff formatting failed"
}

try {
    ruff check . --fix 2>&1 | Out-Null
    Log "Ruff auto-fixes applied"
} catch {
    Log "Ruff auto-fixes failed"
}

Log "Sort imports"
try {
    isort . 2>&1 | Out-Null
    Log "Import sorting completed"
} catch {
    Log "Import sorting failed"
}

Log "Run flake8 and save"
try {
    flake8 app tests 2>&1 | Set-Content "$ART/flake8_after_autofix.txt"
    Log "Flake8 check completed"
} catch {
    Log "Flake8 check failed"
}

Log "Run mypy (narrow scope) and save"
try {
    mypy app/api app/repos app/models --ignore-missing-imports 2>&1 | Set-Content "$ART/mypy_after_autofix.txt"
    Log "MyPy check completed"
} catch {
    Log "MyPy check failed"
}

Log "Run pytest and save"
try {
    pytest -q --maxfail=1 --disable-warnings 2>&1 | Tee-Object -FilePath "$ART/pytest_after_autofix.log"
    Log "Pytest completed"
} catch {
    Log "Pytest failed"
}

# Check for npm and frontend build
try {
    npm --version | Out-Null
    if (Test-Path "web/admin") {
        Log "Attempting frontend build (npm)..."
        try {
            Set-Location "web/admin"
            npm ci --silent 2>&1 | Set-Content "../../$ART/npm_install.log"
            Set-Location "../.."
            Log "npm ci completed"
        } catch {
            Log "npm ci failed; see $ART/npm_install.log"
        }
        
        try {
            Set-Location "web/admin"
            npm run build --silent 2>&1 | Set-Content "../../$ART/npm_build.log"
            Set-Location "../.."
            Log "npm build completed"
        } catch {
            Log "npm build failed; see $ART/npm_build.log"
        }
    } else {
        Log "web/admin directory not found"
    }
} catch {
    Log "npm not available; skipping frontend build"
}

Log "Packaging artifacts"
try {
    Compress-Archive -Path $ART -DestinationPath "$ART.zip" -Force
    Log "Artifacts packaged as $ART.zip"
} catch {
    Log "Failed to package artifacts"
}

Set-Content -Path "$ART/ARTIFACT_DIR_PATH.txt" -Value $ART
Log "Done. Artifacts: $ART"
