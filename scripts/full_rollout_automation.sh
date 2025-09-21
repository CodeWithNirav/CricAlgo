#!/bin/bash
set -euo pipefail

# Full automated PR -> Canary -> Merge -> Release -> Runbook flow
# CricAlgo Performance Rollout Automation Script

# == CONFIG (edit before run if needed) ==
BRANCH="${BRANCH:-perf/full-rollout-b5d16280-$(date -u +%Y%m%dT%H%M%SZ)}"
PR_TITLE="${PR_TITLE:-perf: full rollout — webhook quick-return + instrumentation + nginx LB + HPA + alerts}"
PR_BODY_FILE=".github/PR_BODY.md"
PR_REVIEWERS="${PR_REVIEWERS:-backend-lead,devops}"
PR_LABELS="${PR_LABELS:-perf,staging-tested}"
RELEASE_TAG="${RELEASE_TAG:-v1.0.0}"
CANARY_STRATEGY="${CANARY_STRATEGY:-istio}"   # istio or nginx
CANARY_WEIGHTS=(10 25 50 100)
SMOKE_VUS=${SMOKE_VUS:-20}
SMOKE_DURATION=${SMOKE_DURATION:-60s}
LONG_K6_VUS=${LONG_K6_VUS:-100}
LONG_K6_DURATION=${LONG_K6_DURATION:-5m}
TIMEOUT_CI=${TIMEOUT_CI:-1800}   # 30 minutes
DRY_RUN=${DRY_RUN:-false}        # Set to true for dry run mode
ARTIFACT_DIR="artifacts/full_rollout_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ARTIFACT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$ARTIFACT_DIR/automation.log"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$ARTIFACT_DIR/automation.log"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$ARTIFACT_DIR/automation.log"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$ARTIFACT_DIR/automation.log"
}

# == PRECHECKS ==
log_info "Starting CricAlgo Full Rollout Automation"
log_info "Branch: $BRANCH"
log_info "Strategy: $CANARY_STRATEGY"
log_info "Artifacts: $ARTIFACT_DIR"
if [ "$DRY_RUN" = "true" ]; then
    log_warning "DRY RUN MODE ENABLED - No production changes will be made"
fi

# Must have GITHUB_TOKEN set for API operations
if [ -z "${GITHUB_TOKEN:-}" ]; then
  log_error "GITHUB_TOKEN is required in env for PR/Release automation. Aborting."
  exit 2
fi

if [ -z "${STAGING_HOST:-}" ]; then
  log_warning "STAGING_HOST not set. Defaulting to http://localhost:8000"
  STAGING_HOST="http://localhost:8000"
fi

# Ensure clean git state
if ! git status --porcelain > /dev/null 2>&1; then
  log_error "Not a git repo or git not available"
  exit 2
fi

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
  log_warning "Not on main branch (current: $CURRENT_BRANCH). Switching to main..."
  git checkout main
fi

# Create branch from current HEAD
log_info "Creating feature branch: $BRANCH"
git checkout -b "$BRANCH"
git add -A || true
git commit -m "chore(perf): prepare full rollout automation artifacts" || true
git push -u origin "$BRANCH"

# == Step 1: Open PR ==
log_info "Opening PR..."
if command -v gh >/dev/null 2>&1; then
  gh pr create --title "$PR_TITLE" --body-file "$PR_BODY_FILE" --base main --head "$BRANCH" --label $(echo $PR_LABELS | sed 's/,/ --label /g') --reviewer $(echo $PR_REVIEWERS | sed 's/,/ --reviewer /g') || true
else
  # fallback: GitHub API create PR
  API_PAYLOAD=$(jq -n --arg t "$PR_TITLE" --arg h "$BRANCH" --arg b "$(cat $PR_BODY_FILE)" --arg base "main" '{title:$t, head:$h, base:$base, body:$b}')
  curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/CodeWithNirav/CricAlgo/pulls" -d "$API_PAYLOAD" | tee "$ARTIFACT_DIR/pr_create.json"
fi

# Grab PR URL (best-effort)
PR_URL=$(gh pr view --json url -q .url 2>/dev/null || true)
log_success "PR opened: $PR_URL"
echo "$PR_URL" > "$ARTIFACT_DIR/pr_info.txt"

# == Step 2: Wait for CI to pass (timeout) ==
log_info "Waiting for CI (timeout ${TIMEOUT_CI}s)..."
START=$(date +%s)
CI_PASSED=false

while true; do
  # Use gh to check checks; fallback to API
  if command -v gh >/dev/null 2>&1 && [ -n "$PR_URL" ]; then
    PR_NUM=$(basename "$PR_URL")
    CHECKS_STATUS=$(gh pr checks "$PR_NUM" --json conclusion -q '.[0].conclusion' 2>/dev/null || true)
    if [ "$CHECKS_STATUS" = "SUCCESS" ] || [ "$CHECKS_STATUS" = "COMPLETED" ]; then
      CI_PASSED=true
      break
    fi
  else
    # Try to inspect latest commit status
    SHA=$(git rev-parse HEAD)
    STATE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/repos/CodeWithNirav/CricAlgo/commits/$SHA/status" | jq -r .state)
    if [ "$STATE" = "success" ]; then CI_PASSED=true; break; fi
  fi
  NOW=$(date +%s)
  ELAPSED=$((NOW-START))
  if [ $ELAPSED -gt $TIMEOUT_CI ]; then
    log_warning "CI timeout after $TIMEOUT_CI seconds. Capturing checks and continuing with caution."
    break
  fi
  sleep 10
done

echo "CI status: $CI_PASSED" > "$ARTIFACT_DIR/ci_status.txt"

# Optional: pause for manual review if CI not passed
if [ "$CI_PASSED" != "true" ]; then
  log_warning "CI did not report success. Pausing for manual review is recommended."
  echo "Proceed? (yes/no)"
  read PROCEED
  if [ "$PROCEED" != "yes" ]; then
    log_error "Aborting as per user choice."
    exit 1
  fi
fi

# == Step 3: Canary deployment ==
log_info "Preparing canary deployment using strategy: $CANARY_STRATEGY"

confirm_proceed() {
  if [ "$DRY_RUN" = "true" ]; then
    log_info "DRY RUN: Skipping production confirmation (no production changes will be made)"
    return 0
  fi
  
  log_warning "Confirm you want to start the canary in production (this will route a portion of live traffic)."
  echo "Type 'I ACCEPT' to proceed:"
  read ACK
  if [ "$ACK" != "I ACCEPT" ]; then
    log_error "User did not accept. Aborting canary."
    exit 1
  fi
}

confirm_proceed

if [ "$DRY_RUN" = "true" ]; then
  log_info "DRY RUN: Skipping canary deployment (no production changes will be made)"
  log_info "DRY RUN: Would apply $CANARY_STRATEGY canary configuration"
else
  if [ "$CANARY_STRATEGY" = "istio" ]; then
    # Apply Istio canary manifests
    log_info "Applying Istio canary manifests..."
    kubectl -n prod apply -f k8s/istio/virtualservice-canary-10.yaml || { log_error "Failed to apply canary VS"; exit 2; }
    log_success "Canary routing applied: 10% traffic -> canary."
  else
    # nginx path: update upstream weights or apply new upstream conf
    log_info "Applying nginx-based canary (upstream weight 10%)."
    kubectl -n prod apply -f k8s/nginx/upstream-canary-10.yaml || true
  fi

  # Wait for canary pods to be ready
  log_info "Waiting for canary pods..."
  kubectl -n prod rollout status deploy/app-canary --timeout=120s || true
  sleep 10
fi

# == Step 4: Smoke test against canary ==
SMOKE_ART="$ARTIFACT_DIR/canary_smoke"
mkdir -p "$SMOKE_ART"
log_info "Running smoke tests (VUs=$SMOKE_VUS, duration=$SMOKE_DURATION) against canary..."
TARGET="${STAGING_HOST}"
# If Istio, use prod host
if [ "$CANARY_STRATEGY" = "istio" ]; then
  TARGET="https://api.yourdomain.com"
fi

# basic health
curl -sS "$TARGET/api/v1/health" -o "$SMOKE_ART/health.json" || true
# run k6 short smoke
if command -v k6 >/dev/null 2>&1; then
  k6 run --vus $SMOKE_VUS --duration $SMOKE_DURATION load/k6/webhook_test.js --summary-export="$SMOKE_ART/k6_summary.json" | tee "$SMOKE_ART/k6_short_out.txt"
else
  docker run -i --rm -v "$(pwd)":/scripts -w /scripts loadimpact/k6 run --vus $SMOKE_VUS --duration $SMOKE_DURATION /scripts/load/k6/webhook_test.js | tee "$SMOKE_ART/k6_short_out.txt"
fi

# Collect logs & metrics
kubectl -n prod get pods -l app=cricalgo -o wide > "$SMOKE_ART/pods.txt" || true
kubectl -n prod logs -l app=cricalgo --tail=200 > "$SMOKE_ART/app_logs.txt" || true

# Evaluate smoke: require 95% success of checks if present
# Simple pass if k6 returned no errors in stdout (heuristic)
if grep -q "errors" "$SMOKE_ART/k6_short_out.txt" >/dev/null 2>&1; then
  log_error "Smoke test reported errors. Aborting canary promotion. Rolling back."
  # Rollback canary weight to 0 or delete canary VS
  if [ "$CANARY_STRATEGY" = "istio" ]; then
    kubectl -n prod delete -f k8s/istio/virtualservice-canary-10.yaml || true
  fi
  exit 3
fi

log_success "Smoke tests passed. Proceeding with progressive promotion."

# == Step 5: Progressive promotion (10 -> 25 -> 50 -> 100) with checks ==
if [ "$DRY_RUN" = "true" ]; then
  log_info "DRY RUN: Skipping progressive promotion (no production changes will be made)"
  for w in "${CANARY_WEIGHTS[@]}"; do
    log_info "DRY RUN: Would promote canary to weight $w%"
  done
else
  for w in "${CANARY_WEIGHTS[@]}"; do
    log_info "Promoting canary to weight $w%"
    if [ "$CANARY_STRATEGY" = "istio" ]; then
      # Use template file for dynamic weight configuration
      sed "s/WEIGHT_PLACEHOLDER/$w/g" k8s/istio/virtualservice-canary-template.yaml | kubectl -n prod apply -f - || true
    else
      # nginx route modification script
      kubectl -n prod apply -f "k8s/nginx/upstream-canary-$w.yaml" || true
    fi
    # wait & run short checks
    log_info "Waiting 30s before tests..."
    sleep 30
    # run short k6
    if command -v k6 >/dev/null 2>&1; then
      k6 run --vus 20 --duration 30s load/k6/webhook_test.js --summary-export="$ARTIFACT_DIR/k6_promote_${w}.json" | tee "$ARTIFACT_DIR/k6_promote_${w}.txt"
    else
      docker run -i --rm -v "$(pwd)":/scripts -w /scripts loadimpact/k6 run --vus 20 --duration 30s /scripts/load/k6/webhook_test.js | tee "$ARTIFACT_DIR/k6_promote_${w}.txt"
    fi
    # basic health check
    curl -sS "$TARGET/api/v1/health" -o "$ARTIFACT_DIR/health_promote_${w}.json" || true
    # evaluate (simple heuristic: error string presence)
    if grep -q "errors" "$ARTIFACT_DIR/k6_promote_${w}.txt" >/dev/null 2>&1; then
      log_error "Promotion to $w% found errors. Rolling back to previous stable."
      # attempt rollback
      if [ "$CANARY_STRATEGY" = "istio" ]; then
        kubectl -n prod delete -f k8s/istio/virtualservice-canary-10.yaml || true
      fi
      exit 4
    fi
    log_success "Promotion to $w% successful"
  done
fi

# If we reach here, promotion succeeded up to 100%
log_success "Canary promoted to 100% successfully."

# == Step 6: Merge PR into main ==
if [ "$DRY_RUN" = "true" ]; then
  log_info "DRY RUN: Skipping PR merge and release creation (no production changes will be made)"
  log_info "DRY RUN: Would merge PR $PR_URL to main"
  log_info "DRY RUN: Would create release $RELEASE_TAG"
else
  log_info "Merging PR branch to main..."
  git checkout main
  git pull origin main
  git merge --no-ff "$BRANCH" -m "merge: perf rollout $(date -u)" || true
  git push origin main

  # Create release tag and GitHub release
  git tag -a "$RELEASE_TAG" -m "Release $RELEASE_TAG - performance rollout"
  git push origin "$RELEASE_TAG"
  # create GitHub release
  if command -v gh >/dev/null 2>&1; then
    gh release create "$RELEASE_TAG" --title "$RELEASE_TAG" --notes "Performance rollout release. See artifacts." || true
  else
    # fallback: GitHub API
    curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" -d "$(jq -n --arg tag "$RELEASE_TAG" --arg body "Performance rollout release" '{tag_name:$tag, name:$tag, body:$body}')" "https://api.github.com/repos/CodeWithNirav/CricAlgo/releases" > "$ARTIFACT_DIR/release_create.json" || true
  fi

  log_success "Release $RELEASE_TAG created"
fi

# == Step 7: Generate runbook PDF (simple markdown->PDF using pandoc if available) ==
RUNBOOK_MD="docs/runbook_prod_rollout.md"
RUNBOOK_PDF="$ARTIFACT_DIR/runbook_prod_rollout.pdf"
if [ -f "$RUNBOOK_MD" ]; then
  if command -v pandoc >/dev/null 2>&1; then
    pandoc "$RUNBOOK_MD" -o "$RUNBOOK_PDF" || true
  else
    cp "$RUNBOOK_MD" "$ARTIFACT_DIR/runbook_prod_rollout.md"
  fi
fi

# == Step 8: Collect final artifacts & pack ==
tar -czf "$ARTIFACT_DIR.tar.gz" -C "$(dirname "$ARTIFACT_DIR")" "$(basename "$ARTIFACT_DIR")" || true
log_success "Artifacts saved at $ARTIFACT_DIR and $ARTIFACT_DIR.tar.gz"

# Final status
cat > "$ARTIFACT_DIR/final_status.json" <<EOF
{
  "branch": "$BRANCH",
  "pr_url": "$PR_URL",
  "release_tag": "$RELEASE_TAG",
  "artifact": "$ARTIFACT_DIR.tar.gz",
  "canary_strategy": "$CANARY_STRATEGY",
  "promoted": true,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

log_success "=== Full rollout complete ==="
log_info "Artifacts: $ARTIFACT_DIR"
log_info "Final status: $(cat $ARTIFACT_DIR/final_status.json)"
exit 0
