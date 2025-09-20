import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const webhookSuccessRate = new Rate('webhook_success_rate');
const webhookResponseTime = new Trend('webhook_response_time');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 }, // Ramp up to 10 users
    { duration: '5m', target: 10 }, // Stay at 10 users
    { duration: '2m', target: 20 }, // Ramp up to 20 users
    { duration: '5m', target: 20 }, // Stay at 20 users
    { duration: '2m', target: 0 },  // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests must complete below 2s
    http_req_failed: ['rate<0.1'],     // Error rate must be below 10%
    webhook_success_rate: ['rate>0.9'], // Webhook success rate must be above 90%
  },
};

// Test data
const webhookPayloads = [
  {
    type: 'deposit',
    data: {
      tx_hash: '0x1234567890abcdef',
      amount: '100.00',
      currency: 'USDT',
      user_id: 'user123',
      status: 'confirmed'
    }
  },
  {
    type: 'contest_result',
    data: {
      contest_id: 'contest123',
      user_id: 'user123',
      position: 1,
      prize_amount: '50.00',
      status: 'won'
    }
  },
  {
    type: 'withdrawal',
    data: {
      tx_hash: '0xabcdef1234567890',
      amount: '25.00',
      currency: 'USDT',
      user_id: 'user123',
      status: 'pending'
    }
  }
];

export default function() {
  // Test webhook endpoint
  const payload = webhookPayloads[Math.floor(Math.random() * webhookPayloads.length)];
  const headers = {
    'Content-Type': 'application/json',
    'X-Webhook-Secret': 'test-webhook-secret'
  };
  
  const startTime = Date.now();
  const response = http.post(`${__ENV.BASE_URL || 'http://localhost:8000'}/api/v1/webhooks`, 
    JSON.stringify(payload), 
    { headers }
  );
  const endTime = Date.now();
  
  // Record metrics
  const success = check(response, {
    'webhook status is 200': (r) => r.status === 200,
    'webhook response time < 2s': (r) => r.timings.duration < 2000,
    'webhook has correct content type': (r) => r.headers['Content-Type'] === 'application/json',
  });
  
  webhookSuccessRate.add(success);
  webhookResponseTime.add(endTime - startTime);
  
  // Test health endpoint
  const healthResponse = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}/health`);
  check(healthResponse, {
    'health check status is 200': (r) => r.status === 200,
  });
  
  // Test metrics endpoint
  const metricsResponse = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}/metrics`);
  check(metricsResponse, {
    'metrics endpoint status is 200': (r) => r.status === 200,
    'metrics contains prometheus data': (r) => r.body.includes('http_requests_total'),
  });
  
  // Test API endpoints
  const apiEndpoints = [
    '/api/v1/health',
    '/api/v1/wallet/balance',
    '/api/v1/contest/list',
  ];
  
  for (const endpoint of apiEndpoints) {
    const apiResponse = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}${endpoint}`);
    check(apiResponse, {
      [`${endpoint} status is not 500`]: (r) => r.status !== 500,
    });
  }
  
  sleep(1);
}

export function handleSummary(data) {
  return {
    'load-test-results.json': JSON.stringify(data, null, 2),
    'load-test-summary.txt': `
Load Test Summary
================
Duration: ${data.state.testRunDurationMs / 1000}s
VUs: ${data.metrics.vus.values.max}
Requests: ${data.metrics.http_reqs.values.count}
Failed Requests: ${data.metrics.http_req_failed.values.count}
Success Rate: ${(1 - data.metrics.http_req_failed.values.rate) * 100}%
Avg Response Time: ${data.metrics.http_req_duration.values.avg}ms
95th Percentile: ${data.metrics.http_req_duration.values['p(95)']}ms
Webhook Success Rate: ${data.metrics.webhook_success_rate.values.rate * 100}%
    `,
  };
}
