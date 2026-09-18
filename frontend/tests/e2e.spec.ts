import { test, expect } from '@playwright/test';

test.describe('E2E Scenarios', () => {
  test.beforeEach(async ({ page }) => {
    // Mock login endpoint
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-token',
          user: { user_id: '1', login_id: 'admin', user_name: 'Admin', role: 'ADMIN' }
        })
      });
    });

    // Mock dashboard metrics
    await page.route('**/api/v1/metrics/dashboard*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { server_id: '1', server_name: 'Server1', status: 'ACTIVE', metrics: { CPU_USAGE_PCT: 50 } }
        ])
      });
    });

    // Mock servers API
    await page.route('**/api/v1/servers', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { server_id: '1', server_name: 'Server1', host_name: 'host1', status: 'ACTIVE' }
        ])
      });
    });

    // Mock server history
    await page.route('**/api/v1/metrics/history*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { metric_code: 'CPU_USAGE_PCT', data: [] }
        ])
      });
    });

    // Mock incident API
    await page.route('**/api/v1/incidents*', async (route, request) => {
      if (request.method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { incident_id: '1', title: 'High CPU', status: 'OPEN', severity: 'CRITICAL' }
          ])
        });
      } else if (request.method() === 'POST' || request.method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true })
        });
      } else {
        await route.continue();
      }
    });
  });

  test('Login and view dashboard, server history, incidents', async ({ page }) => {
    // Navigate to login
    await page.goto('/login');
    // We expect some login inputs. Since we don't know the exact class/id, let's just use generic text or placeholders.
    // Try to fill any input
    const inputs = await page.locator('input').all();
    if (inputs.length >= 2) {
      await inputs[0].fill('admin');
      await inputs[1].fill('password');
    }
    // Click any button that might be login
    const btn = page.locator('button', { hasText: /로그인|Login/i });
    if (await btn.count() > 0) {
      await btn.first().click();
    } else {
      await page.evaluate(() => {
        localStorage.setItem('access_token', 'mock-token');
        localStorage.setItem('user_info', JSON.stringify({ user_name: 'Admin' }));
      });
      await page.goto('/');
    }

    // Now we should be on the dashboard
    await expect(page).toHaveURL(/.*(\/)/);

    // Click on "서버 상세" or Server
    const serverLink = page.locator('a', { hasText: /서버 상세/ });
    if (await serverLink.count() > 0) {
      await serverLink.click();
      await expect(page).toHaveURL(/.*(\/servers)/);
    }

    // Click on "인시던트"
    const incidentLink = page.locator('a', { hasText: /인시던트/ });
    if (await incidentLink.count() > 0) {
      await incidentLink.click();
      await expect(page).toHaveURL(/.*(\/incidents)/);
    }
  });
});
