## Summary

This PR implements the performance and resilience rollout for CricAlgo staging:

- **Webhook handler:** quick-return pattern with canonical `{ "ok": true, "tx_id": ... }` response and resilient behavior when user metadata is missing.
- **Instrumentation:** timing logs for webhook enqueue (`deposit_enqueued`) and deposit processing tasks (`deposit_task_started`, `deposit_task_completed`).
- **DB tuning:** environment-configured SQLAlchemy pool settings (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`).
- **Staging load balancing:** nginx + 3 app instances in `docker-compose.staging.yml` for local staging.
- **Kubernetes autoscaling:** HPA manifests for `app` and `worker` (staging).
- **Monitoring:** Prometheus alert rules for latency, error rate and Celery queue depth.
- **Tests:** smoke and 5-minute k6 load test results included as artifacts (see `artifacts/perf_full_run_*`).

## Why
Staging performance tests revealed a single-app bottleneck; after horizontal scaling, instrumentation and task decoupling, we achieved stable, zero-error runs under high load. This PR enables horizontal scale, observability, and autoscaling for production readiness.

## Files changed
- `app/api/v1/webhooks.py` — webhook quick-return + enqueue
- `app/tasks/deposits.py` — instrumentation logs
- `app/db/session.py` — DB pool from env
- `docker-compose.staging.yml` & `deploy/nginx.conf` — local LB & multi-app
- `k8s/hpa/app-hpa.yaml` & `k8s/hpa/worker-hpa.yaml` — HPA
- `monitoring/prometheus/alerts/cricalgo_alerts.yaml` — alert rules
- `PERFORMANCE_ROLLOUT_SUMMARY.md`, `scripts/smoke_and_checks.sh`, `load/k6/webhook_test.js`
- `artifacts/perf_full_run_<timestamp>/` — test artifacts

## Acceptance Criteria (please verify)
- [ ] CI: unit and integration tests pass
- [ ] Migrations validated and run on staging
- [ ] Prometheus reload with new alert rules (staging)
- [ ] Smoke test (10 VUs × 30s) passes
- [ ] Long k6 test (100 VUs × 5m) run with acceptable metrics (error_rate < 1%, p95 < 4s)
- [ ] Reviewers: sign-off from backend and ops

## How to validate locally (staging)
1. Start staging:
   ```bash
   docker-compose -f docker-compose.staging.yml up -d --build nginx app1 app2 app3
   docker-compose -f docker-compose.staging.yml up -d --scale worker=4
   ```

2. Quick smoke:
   ```bash
   ./scripts/smoke_and_checks.sh
   ```

3. Long load:
   ```bash
   k6 run --vus 100 --duration 5m load/k6/webhook_test.js --summary-export=artifacts/k6_summary.json
   ```

## Rollback

* Docker-compose: restore `docker-compose.staging.yml.bak` and `docker-compose -f docker-compose.staging.yml up -d`
* K8s: `kubectl -n <env> rollout undo deploy/app`

## Artifacts

Test artifacts saved under `artifacts/perf_full_run_*` within this repo. Please download them from CI job or from the artifacts folder and attach to this PR for reviewer inspection.

---

**Request reviewers:** @backend-lead, @devops
**Labels:** perf, staging-tested, needs-review
