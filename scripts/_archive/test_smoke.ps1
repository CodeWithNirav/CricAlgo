# PowerShell script to test smoke test functionality
# This script simulates the make targets for Windows

Write-Host "CricAlgo Smoke Test - Windows PowerShell Script" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Function to run smoke test
function Test-SmokeTest {
    Write-Host "Testing smoke test script..." -ForegroundColor Yellow
    
    # Test if the script can be imported
    try {
        python -c "import scripts.smoke_test; print('Smoke test script imports successfully')"
        Write-Host "✓ Import test passed" -ForegroundColor Green
    } catch {
        Write-Host "✗ Import test failed: $_" -ForegroundColor Red
        return $false
    }
    
    # Test if the script can be created
    try {
        python -c "from scripts.smoke_test import SmokeTestRunner; runner = SmokeTestRunner(); print('Smoke test runner created successfully')"
        Write-Host "✓ Runner creation test passed" -ForegroundColor Green
    } catch {
        Write-Host "✗ Runner creation test failed: $_" -ForegroundColor Red
        return $false
    }
    
    # Test help functionality
    try {
        $helpOutput = python scripts/smoke_test.py --help 2>&1
        if ($helpOutput -match "usage:") {
            Write-Host "✓ Help functionality works" -ForegroundColor Green
        } else {
            Write-Host "✗ Help functionality failed" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "✗ Help test failed: $_" -ForegroundColor Red
        return $false
    }
    
    return $true
}

# Function to check Docker availability
function Test-Docker {
    Write-Host "Checking Docker availability..." -ForegroundColor Yellow
    
    try {
        docker --version | Out-Null
        Write-Host "✓ Docker is available" -ForegroundColor Green
        
        docker-compose --version | Out-Null
        Write-Host "✓ Docker Compose is available" -ForegroundColor Green
        
        return $true
    } catch {
        Write-Host "✗ Docker or Docker Compose not available" -ForegroundColor Red
        Write-Host "  Please install Docker Desktop for Windows" -ForegroundColor Yellow
        return $false
    }
}

# Function to check Python dependencies
function Test-PythonDeps {
    Write-Host "Checking Python dependencies..." -ForegroundColor Yellow
    
    try {
        python -c "import httpx, sqlalchemy, fastapi; print('Required dependencies available')"
        Write-Host "✓ Python dependencies check passed" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "✗ Missing Python dependencies" -ForegroundColor Red
        Write-Host "  Run: pip install -r requirements.txt" -ForegroundColor Yellow
        return $false
    }
}

# Main test execution
Write-Host "`nRunning smoke test validation..." -ForegroundColor Cyan

$allTestsPassed = $true

# Test Python dependencies
if (-not (Test-PythonDeps)) {
    $allTestsPassed = $false
}

# Test smoke test script
if (-not (Test-SmokeTest)) {
    $allTestsPassed = $false
}

# Test Docker availability
if (-not (Test-Docker)) {
    $allTestsPassed = $false
}

# Summary
Write-Host "`n" + "="*50 -ForegroundColor Cyan
if ($allTestsPassed) {
    Write-Host "✓ All smoke test validations passed!" -ForegroundColor Green
    Write-Host "`nTo run the full smoke test:" -ForegroundColor Yellow
    Write-Host "1. Start services: docker-compose -f docker-compose.test.yml up -d --build" -ForegroundColor White
    Write-Host "2. Wait 30 seconds for services to be ready" -ForegroundColor White
    Write-Host "3. Run test: python scripts/smoke_test.py" -ForegroundColor White
    Write-Host "4. Check results: artifacts/smoke_test_result.json" -ForegroundColor White
    Write-Host "5. Clean up: docker-compose -f docker-compose.test.yml down -v" -ForegroundColor White
} else {
    Write-Host "✗ Some validations failed. Please fix the issues above." -ForegroundColor Red
}
Write-Host "="*50 -ForegroundColor Cyan
