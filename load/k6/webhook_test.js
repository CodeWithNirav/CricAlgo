import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  vus: 50,
  duration: '60s',
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.02'], // Error rate must be below 2%
  },
};

const BASE_URL = __ENV.STAGING_HOST || 'http://host.docker.internal:8000';
const WEBHOOK_SECRET = __ENV.WEBHOOK_SECRET || 'your-webhook-secret-key';

export default function() {
  // Test webhook endpoint
  const webhookPayload = {
    tx_hash: `0x${Math.random().toString(16).substr(2, 64)}`,
    confirmations: 12,
    chain: 'bep20',
    to_address: '0x1234567890123456789012345678901234567890',
    amount: '20.0',
    currency: 'USDT',
    status: 'confirmed',
    block_number: Math.floor(Math.random() * 1000000) + 1000000,
    user_id: 'a59b0893-0f43-43c8-83aa-87a0dff98338', // Test user ID
    metadata: {
      telegram_user_id: 693173957
    }
  };

  const headers = {
    'Content-Type': 'application/json',
  };

  // Add HMAC signature if secret is provided
  if (WEBHOOK_SECRET && WEBHOOK_SECRET !== 'your-webhook-secret-key') {
    const crypto = require('crypto');
    const signature = crypto
      .createHmac('sha256', WEBHOOK_SECRET)
      .update(JSON.stringify(webhookPayload))
      .digest('hex');
    headers['X-Webhook-Signature'] = `sha256=${signature}`;
  }

  const response = http.post(`${BASE_URL}/api/v1/webhooks/bep20`, JSON.stringify(webhookPayload), {
    headers: headers,
  });

  check(response, {
    'webhook status is 200': (r) => r.status === 200,
    'webhook response time < 500ms': (r) => r.timings.duration < 500,
    'webhook response has ok field': (r) => r.json('ok') === true,
  });

  // Also test health endpoint
  const healthResponse = http.get(`${BASE_URL}/api/v1/health`);
  
  check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
    'health response time < 100ms': (r) => r.timings.duration < 100,
  });

  sleep(1);
}