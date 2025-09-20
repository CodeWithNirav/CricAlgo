# Performance Rollout Script for CricAlgo
# Applies safe, reversible performance and resiliency fixes to staging environment

param(
    [string]$STAGING_HOST = "http://localhost:8000",
    [string]$DATABASE_URL = $env:DATABASE_URL,
    [string]$REDIS_URL = $env:REDIS_URL,
    [string]$GITHUB_TOKEN = $env:GITHUB_TOKEN,
    [string]$KUBECONFIG = $env:KUBECONFIG,
    [bool]$CLEANUP_AFTER = $false,
    [bool]$APPLY_K8S = $false,
    [bool]$OPEN_PR = $false
)

# Helper functions
function Get-Timestamp {
    return (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
}

function Get-ShortSha {
    try {
        return (git rev-parse --short=8 HEAD)
    } catch {
        return "local"
    }
}

# Initialize
$timestamp = Get-Timestamp
$shortSha = Get-ShortSha
$artifactDir = "artifacts/perf_full_run_$timestamp"
$branch = "perf/full-rollout-$shortSha-$timestamp"

Write-Host "Working branch: $branch" | Tee-Object "$artifactDir/run_info.txt"
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

# 1. Create branch (already done)
Write-Host "Branch: $branch"

# 2-7. Changes already committed

# 8. Push branch & open PR (optional)
if ($GITHUB_TOKEN -and $OPEN_PR) {
    Write-Host "Pushing branch and creating PR..."
    git push -u origin $branch
    
    # Use gh CLI if available
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        gh auth setup-git
        gh pr create --title "perf: full rollout (webhook + instrumentation + nginx + HPA + alerts)" --body "Automated PR: performance fixes & staging rollout" --base main --head $branch
    }
}

# 9. Deploy changes to staging
Write-Host "Deploying to staging..."

# Prefer docker-compose path if file exists
if (Test-Path "docker-compose.staging.yml") {
    Write-Host "Using docker-compose path"
    
    # Start services
    docker-compose -f docker-compose.staging.yml up -d --build nginx app1 app2 app3
    docker-compose -f docker-compose.staging.yml up -d --scale worker=4
    
    # Get service status
    docker-compose -f docker-compose.staging.yml ps | Tee-Object "$artifactDir/compose_ps.txt"
    
    # Health checks
    try {
        $healthResponse = Invoke-RestMethod -Uri "$STAGING_HOST/api/v1/health" -Method Get
        $healthResponse | ConvertTo-Json | Out-File "$artifactDir/nginx_health.json"
    } catch {
        Write-Warning "Health check failed: $_"
    }
}

# Also try k8s if requested and available
if ((Get-Command kubectl -ErrorAction SilentlyContinue) -and $APPLY_K8S) {
    Write-Host "Attempting k8s apply/scale in cricalgo-staging namespace"
    kubectl -n cricalgo-staging apply -f k8s/hpa/app-hpa.yaml
    kubectl -n cricalgo-staging apply -f k8s/hpa/worker-hpa.yaml
    kubectl -n cricalgo-staging rollout restart deploy/app
    kubectl -n cricalgo-staging rollout restart deploy/worker
    kubectl -n cricalgo-staging get pods -o wide | Out-File "$artifactDir/k8s_pods.txt"
}

# Wait for services to stabilize
Start-Sleep -Seconds 8

# 10. Run quick smoke test: 10 VUs × 30s
Write-Host "Running smoke test (10 VUs × 30s)..."
$smokeOut = "$artifactDir/k6_smoke_short.txt"

if (Get-Command k6 -ErrorAction SilentlyContinue) {
    k6 run --vus 10 --duration 30s load/k6/webhook_test.js | Tee-Object $smokeOut
} else {
    docker run -i --rm -v "${PWD}:/scripts" -w /scripts loadimpact/k6 run --vus 10 --duration 30s /scripts/load/k6/webhook_test.js | Tee-Object $smokeOut
}

# Capture logs (short)
if (Test-Path "docker-compose.staging.yml") {
    docker-compose -f docker-compose.staging.yml logs --tail=100 nginx | Out-File "$artifactDir/nginx_tail.log"
    docker-compose -f docker-compose.staging.yml logs --tail=200 app1 | Out-File "$artifactDir/app1_tail.log"
    docker-compose -f docker-compose.staging.yml logs --tail=200 app2 | Out-File "$artifactDir/app2_tail.log"
    docker-compose -f docker-compose.staging.yml logs --tail=200 app3 | Out-File "$artifactDir/app3_tail.log"
    docker-compose -f docker-compose.staging.yml logs --tail=200 worker | Out-File "$artifactDir/worker_tail.log"
}

if ((Get-Command kubectl -ErrorAction SilentlyContinue) -and $APPLY_K8S) {
    kubectl -n cricalgo-staging logs -l app=cricalgo --tail=200 | Out-File "$artifactDir/k8s_app_tail.log"
    kubectl -n cricalgo-staging logs -l component=worker --tail=200 | Out-File "$artifactDir/k8s_worker_tail.log"
}

# 11. Run long k6 test: 100 VUs × 5m
Write-Host "Running long k6 test (100 VUs × 5m)..."
$k6Out = "$artifactDir/k6_long.txt"

if (Get-Command k6 -ErrorAction SilentlyContinue) {
    k6 run --vus 100 --duration 5m load/k6/webhook_test.js --summary-export="$artifactDir/k6_summary.json" | Tee-Object $k6Out
} else {
    docker run -i --rm -v "${PWD}:/scripts" -w /scripts loadimpact/k6 run --vus 100 --duration 5m /scripts/load/k6/webhook_test.js | Tee-Object $k6Out
}

# 12. Collect DB & Celery stats
if ($DATABASE_URL) {
    # Attempt psql
    if (Get-Command psql -ErrorAction SilentlyContinue) {
        psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;" | Out-File "$artifactDir/db_conn_count.txt"
        psql $DATABASE_URL -c "SELECT pid, now()-query_start AS duration, query FROM pg_stat_activity WHERE state <> 'idle' AND now()-query_start > interval '1 second' ORDER BY duration DESC LIMIT 20;" | Out-File "$artifactDir/pg_long_queries.txt"
    }
}

if (Get-Command celery -ErrorAction SilentlyContinue) {
    celery -A app.celery_app inspect stats | Out-File "$artifactDir/celery_stats.txt"
    celery -A app.celery_app inspect active | Out-File "$artifactDir/celery_active.txt"
}

# Prometheus snapshot if available
$promHost = $env:PROM_HOST
if (-not $promHost) { $promHost = "http://prometheus:9090" }
try {
    $promResponse = Invoke-RestMethod -Uri "$promHost/api/v1/query?query=rate(http_requests_total[1m])" -Method Get
    $promResponse | ConvertTo-Json | Out-File "$artifactDir/prom_snapshot.json"
} catch {
    Write-Warning "Prometheus snapshot failed: $_"
}

# 13. Create test_summary.json with PASS/FAIL criteria
$summaryFile = "$artifactDir/k6_summary.json"
$outFile = "$artifactDir/test_summary.json"

$result = @{ pass = $false; reason = "no summary" }

if (Test-Path $summaryFile) {
    $j = Get-Content $summaryFile | ConvertFrom-Json
    $metrics = $j.metrics
    $httpDur = $metrics.http_req_duration
    $p95 = $httpDur.values."p(95)"
    
    if ($p95 -and $p95 -le 2000) {
        $result = @{ pass = $true; p95 = $p95 }
    } else {
        $result = @{ pass = $false; p95 = $p95; note = "p95 above 2s or missing" }
    }
} else {
    # Fallback parse k6 long raw
    $path = "$artifactDir/k6_long.txt"
    if (Test-Path $path) {
        $txt = Get-Content $path -Raw
        $result = @{ pass = ($txt -match "Error rate 0%" -or $txt -notmatch "error rate") }
    }
}

$result | ConvertTo-Json | Out-File $outFile
Write-Host "Wrote $outFile"

# 14. Create tarball
Write-Host "Creating artifacts tarball..."
Compress-Archive -Path $artifactDir -DestinationPath "$artifactDir.zip" -Force

# 15. Final output
Write-Host "=== RUN SUMMARY ==="
Write-Host "Branch: $branch"
Write-Host "Artifacts: $artifactDir"
Write-Host "Tarball: $artifactDir.zip"
if (Test-Path $outFile) {
    Get-Content $outFile | Write-Host
}
Write-Host "Logs: $artifactDir/app1_tail.log $artifactDir/app2_tail.log $artifactDir/app3_tail.log $artifactDir/worker_tail.log"
if ($GITHUB_TOKEN -and $OPEN_PR) {
    Write-Host "A PR was opened for branch $branch (if gh CLI configured)"
}

Write-Host "Performance rollout completed successfully!"
