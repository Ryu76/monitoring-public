import { test, expect } from '@playwright/test';

test.describe('E2E Scenarios', () => {
  test.beforeEach(async ({ page }) => {
    // Mock login endpoint
    await page.route('**/api/v1/admin/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-token',
          user_info: { user_id: '1', login_id: 'admin', user_name: 'Admin', role: 'ADMIN' }
        })
      });
    });

    // Mock dashboard metrics
    await page.route('**/api/v1/dashboard/summary', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            total_servers: 5,
            normal: 4,
            warning: 0,
            critical: 1,
            unknown: 0,
            total_agents: 5,
            online_agents: 4,
            open_events: 2
          }
        })
      });
    });

    await page.route('**/api/v1/events?status=OPEN', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            { event_uid: 'e1', severity_code: 'CRITICAL', status_code: 'OPEN', title: 'High CPU', message: 'CPU high', first_occurred_at: '2023-01-01T00:00:00Z', occurrence_count: 5 }
          ]
        })
      });
    });

    // Mock servers API
    await page.route('**/api/v1/servers**', async (route, request) => {
      if (request.url().includes('check-targets')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            data: { processes: [], services: [], ports: [] }
          })
        });
      } else if (request.url().match(/\/api\/v1\/servers\/\d+/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            data: { server_id: 1, server_name: 'Server1', host_name: 'host1', mgmt_ip: '10.0.0.1', os_type_code: 'LINUX', composite_status: 'NORMAL', agent_status: 'APPROVED', metrics: [] }
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            data: [
              { server_id: 1, server_name: 'Server1', host_name: 'host1', mgmt_ip: '10.0.0.1', os_type_code: 'LINUX', composite_status: 'NORMAL' }
            ]
          })
        });
      }
    });

    // Mock server metrics history
    await page.route('**/api/v1/metrics/history*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            { metric_code: 'CPU_USAGE_PCT', timestamp: '2023-01-01T00:00:00Z', value: 50.0 }
          ]
        })
      });
    });

    // Mock incident API
    await page.route('**/api/v1/incidents**', async (route, request) => {
      if (request.method() === 'GET') {
        if (request.url().match(/\/api\/v1\/incidents\/\d+/)) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              data: { incident_id: 1, title: 'High CPU', status_code: 'OPEN', impact_code: 'CRITICAL', detected_at: '2023-01-01T00:00:00Z', cause_code: 'UNKNOWN', events: [] }
            })
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              data: [
                { incident_id: 1, incident_title: 'High CPU', status_code: 'OPEN', impact_code: 'CRITICAL', detected_at: '2023-01-01T00:00:00Z' }
              ]
            })
          });
        }
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true })
        });
      }
    });
  });

  test('Login and view dashboard, server history, incidents', async ({ page }) => {
    // Navigate to login
    await page.goto('/login');

    // Explicit assertions for login UI
    const loginIdInput = page.locator('input[placeholder="admin"]');
    const passwordInput = page.locator('input[placeholder="비밀번호 입력"]');
    const loginButton = page.locator('button', { hasText: '로그인' });

    await expect(loginIdInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(loginButton).toBeVisible();

    await loginIdInput.fill('admin');
    await passwordInput.fill('password');
    await loginButton.click();

    // Now we should be on the dashboard
    await expect(page).toHaveURL(/.*(\/)/);

    // Explicit assertions for dashboard content
    await expect(page.locator('h1', { hasText: '대시보드' })).toBeVisible();
    await expect(page.locator('.kpi-value').first()).toHaveText('5'); // total_servers
    await expect(page.locator('td', { hasText: 'High CPU' })).toBeVisible();

    // Navigate to Servers
    const serverLink = page.locator('a', { hasText: '서버 상세' });
    await expect(serverLink).toBeVisible();
    await serverLink.click();
    await expect(page).toHaveURL(/.*(\/servers)/);

    // Explicit assertions for server detail/history rendering
    await expect(page.locator('h1', { hasText: '서버 상세' })).toBeVisible();
    await expect(page.locator('.server-list-item', { hasText: 'Server1' })).toBeVisible();
    await expect(page.locator('.server-list-item', { hasText: '10.0.0.1' })).toBeVisible();
    // Click the server to see details
    await page.locator('.server-list-item', { hasText: 'Server1' }).click();
    // Expect server detail section
    await expect(page.locator('.server-info')).toBeVisible();

    // Navigate to Incidents
    const incidentLink = page.locator('a', { hasText: '인시던트' });
    await expect(incidentLink).toBeVisible();
    await incidentLink.click();
    await expect(page).toHaveURL(/.*(\/incidents)/);

    // Explicit assertions for incident UI
    await expect(page.locator('h1', { hasText: '인시던트' })).toBeVisible();
    await expect(page.locator('.incident-item', { hasText: 'High CPU' })).toBeVisible();
    await expect(page.locator('.incident-item', { hasText: 'CRITICAL' })).toBeVisible();
  });
});
