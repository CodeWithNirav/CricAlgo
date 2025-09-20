import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const webhookResponseTime = new Trend('webhook_response_time');
const webhookSuccessRate = new Rate('webhook_success_rate');
const webhookEnqueueRate = new Rate('webhook_enqueue_rate');
const healthResponseTime = new Trend('health_response_time');
const healthSuccessRate = new Rate('health_success_rate');

export let options = {
  vus: __ENV.VUS ? parseInt(__ENV.VUS) : 100,
  duration: __ENV.DURATION || '5m',
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'], // 95% < 2s, 99% < 5s
    http_req_failed: ['rate<0.005'], // Error rate must be below 0.5%
    webhook_response_time: ['p(95)<1000'], // Webhook p95 < 1s
    webhook_success_rate: ['rate>0.99'], // Webhook success rate > 99%
    health_response_time: ['p(95)<100'], // Health p95 < 100ms
    health_success_rate: ['rate>0.99'], // Health success rate > 99%
  },
};

const TARGET = __ENV.STAGING_HOST || 'http://localhost:8000';
const WEBHOOK_SECRET = __ENV.WEBHOOK_SECRET || 'your-webhook-secret-key';

export default function() {
  const startTime = Date.now();
  
  // Test 1: Health check
  const healthResponse = http.get(`${TARGET}/api/v1/health`);
  
  const healthSuccess = check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
    'health response time < 100ms': (r) => r.timings.duration < 100,
    'health has status field': (r) => r.json('status') === 'healthy' || r.json('status') === 'ok',
  });
  
  healthResponseTime.add(healthResponse.timings.duration);
  healthSuccessRate.add(healthSuccess);
  
  // Test 2: Webhook submission
  const webhookPayload = {
    tx_hash: `k6-${__VU}-${Date.now()}-${Math.random().toString(16).substr(2, 8)}`,
    amount: (Math.random() * 100 + 0.001).toFixed(3), // Random amount between 0.001 and 100.001
    metadata: {
      note: "k6-load-test",
      test_run: __ENV.TEST_RUN || "default",
      virtual_user: __VU,
      iteration: __ITER
    }
  };

  const headers = {
    'Content-Type': 'application/json',
  };

  // Add HMAC signature if secret is provided
  if (WEBHOOK_SECRET && WEBHOOK_SECRET !== 'your-webhook-secret-key') {
    const signature = crypto.hmac('sha256', WEBHOOK_SECRET, JSON.stringify(webhookPayload), 'hex');
    headers['X-Webhook-Signature'] = `sha256=${signature}`;
  }

  const webhookResponse = http.post(`${TARGET}/api/v1/webhooks/bep20`, JSON.stringify(webhookPayload), {
    headers: headers,
  });

  const webhookSuccess = check(webhookResponse, {
    'webhook status is 202': (r) => r.status === 202,
    'webhook response time < 1s': (r) => r.timings.duration < 1000,
    'webhook response has ok field': (r) => r.json('ok') === true,
    'webhook response has tx_id field': (r) => r.json('tx_id') && r.json('tx_id').length > 0,
  });
  
  webhookResponseTime.add(webhookResponse.timings.duration);
  webhookSuccessRate.add(webhookSuccess);
  
  // Check if webhook was enqueued (based on response)
  const enqueued = webhookResponse.status === 202 && webhookResponse.json('ok') === true;
  webhookEnqueueRate.add(enqueued);
  
  // Log detailed response for debugging (only for first few iterations)
  if (__ITER < 3) {
    console.log(`VU ${__VU}, Iteration ${__ITER}:`);
    console.log(`  Health: ${healthResponse.status} (${healthResponse.timings.duration}ms)`);
    console.log(`  Webhook: ${webhookResponse.status} (${webhookResponse.timings.duration}ms)`);
    if (webhookResponse.json('tx_id')) {
      console.log(`  TX ID: ${webhookResponse.json('tx_id')}`);
    }
  }
  
  // Random sleep between 0.5-2 seconds to simulate realistic load
  sleep(Math.random() * 1.5 + 0.5);
}

export function handleSummary(data) {
  return {
    'artifacts/k6_summary.json': JSON.stringify(data, null, 2),
    'artifacts/k6_long.txt': `
K6 Load Test Summary
===================
Test Duration: ${data.state.testRunDurationMs}ms
Virtual Users: ${data.metrics.vus.values.max}
Total Requests: ${data.metrics.http_reqs.values.count}
Failed Requests: ${data.metrics.http_req_failed.values.count}
Error Rate: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%

Response Times:
- Average: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms
- P95: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms
- P99: ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms
- Max: ${data.metrics.http_req_duration.values.max.toFixed(2)}ms

Webhook Metrics:
- Success Rate: ${(data.metrics.webhook_success_rate.values.rate * 100).toFixed(2)}%
- Avg Response Time: ${data.metrics.webhook_response_time.values.avg.toFixed(2)}ms
- P95 Response Time: ${data.metrics.webhook_response_time.values['p(95)'].toFixed(2)}ms

Health Check Metrics:
- Success Rate: ${(data.metrics.health_success_rate.values.rate * 100).toFixed(2)}%
- Avg Response Time: ${data.metrics.health_response_time.values.avg.toFixed(2)}ms
- P95 Response Time: ${data.metrics.health_response_time.values['p(95)'].toFixed(2)}ms

Thresholds:
${Object.entries(data.thresholds).map(([name, result]) => 
  `- ${name}: ${result.ok ? 'PASS' : 'FAIL'} (${result.fails}/${result.passes})`
).join('\n')}
`,
  };
}