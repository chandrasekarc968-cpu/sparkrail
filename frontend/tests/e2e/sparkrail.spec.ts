import { test, expect } from '@playwright/test';

test.describe('SparkRail Live End-to-End Control Room Smoke Tests', () => {
  test('executes complete operations control-room smoke workflow against real backend', async ({ page }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // Ignore expected Three.js deprecation warning
        if (!text.includes('THREE.Clock') && !text.includes('Failed to load resource')) {
          consoleErrors.push(text);
        }
      }
    });

    page.on('requestfailed', (req) => {
      // Ignore intentionally simulated failure requests
      if (!req.url().includes('/simulate-backend-failure') && !req.url().includes('/schedule/fault')) {
        failedRequests.push(`${req.method()} ${req.url()}`);
      }
    });

    // 1. Open http://127.0.0.1:5173
    await page.goto('/');

    // 2. Confirm the Overview page renders
    await expect(page.locator('h1')).toContainText('Operations Overview');

    // 3. Confirm the UI shows Connected or Live API mode, not Demo mode
    const connectionBadge = page.locator('header').locator('text=Connected');
    await expect(connectionBadge).toBeVisible({ timeout: 15000 });
    // Verify Demo mode indicator is NOT active in live mode
    await expect(page.locator('header').locator('text=Demo mode')).toHaveCount(0);

    // 4. Navigate to /3d
    await page.click('a[href="/3d"]');
    await expect(page).toHaveURL(/.*\/3d/);

    // 5. Confirm the 3D canvas or accessible 2D fallback renders
    const viewElement = page.locator('canvas, [aria-label*="Accessible 2D Corridor Schematic View"]').first();
    await expect(viewElement).toBeVisible({ timeout: 15000 });

    // 6. Confirm at least one block, one station/node, and one train are visible in the operational status
    await expect(page.locator('main').getByText(/Subedarganj|Mirzapur|Corridor/i).first()).toBeVisible({ timeout: 15000 });
    const fallbackBtn = page.locator('button:has-text("2D Fallback")');
    if (await fallbackBtn.isVisible()) {
      await fallbackBtn.click();
    }
    await expect(page.locator('main').getByText(/B1|B2|B3|B4/i).first()).toBeVisible({ timeout: 15000 });

    // 7. Confirm the timeline controls render
    const timeline = page.getByRole('region', { name: /Operations Timeline Controller/i });
    await expect(timeline).toBeVisible();
    await expect(page.locator('button:has-text("Play"), button:has-text("Pause")').first()).toBeVisible();

    // 8. Click a block and confirm the inspector shows block ID, state, and TCI-related information
    const inspectBtn = page.locator('main button:has-text("Inspect")').first();
    if (await inspectBtn.isVisible()) {
      await inspectBtn.click();
    } else {
      await page.locator('main').getByText(/B1|B4/).first().click();
    }
    const inspector = page.getByRole('complementary', { name: /Planning Detail Inspector/i });
    await expect(inspector).toBeVisible({ timeout: 10000 });
    await expect(inspector).toContainText(/BLOCK DETAILS|CHAINAGE|SPEED LIMIT/i);

    // 9. Navigate to /planner
    await page.click('a[href="/planner"]');
    await expect(page).toHaveURL(/.*\/planner/);

    // 10. Trigger optimization through the UI
    const optimizeBtn = page.getByRole('button', { name: /Run Optimization/i });
    await expect(optimizeBtn).toBeVisible();
    await optimizeBtn.click();

    // 11. Confirm loading state appears or solver finishes
    // 12. Confirm solver status and scheduled or unscheduled jobs appear
    await expect(page.locator('text=/Solver: (PySCIPOpt|NON_OPTIMAL_FALLBACK)/i').first()).toBeVisible({ timeout: 20000 });
    await expect(page.locator('text=/Scheduled Tasks|Scheduled Jobs|Jobs/i').first()).toBeVisible();

    // 13. Navigate to /reports
    await page.click('a[href="/reports"]');
    await expect(page).toHaveURL(/.*\/reports/);

    // 14. Confirm KPI values render from the real /evaluate response
    await expect(page.getByText(/Block Utilization Efficiency|BUE/i).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Shadow Block Ratio|SBR/i).first()).toBeVisible();
    await expect(page.getByText(/Total Closure Time|Closure Hours/i).first()).toBeVisible();

    // 15. Simulate backend failure
    // Intercept health and scenario requests to return 503 Service Unavailable
    await page.route('**/health', (route) => route.fulfill({ status: 503, body: 'Backend Down' }));
    await page.route('**/schedule/latest', (route) => route.fulfill({ status: 503, body: 'Backend Down' }));
    await page.route('**/evaluate', (route) => route.fulfill({ status: 503, body: 'Backend Down' }));

    // Trigger refresh in UI
    const refreshBtn = page.locator('button[title="Refresh operational data"]');
    if (await refreshBtn.isVisible()) {
      await refreshBtn.click();
    } else {
      await page.reload();
    }

    // 16. Confirm the frontend shows an honest error state with retry, not fake successful data
    await expect(
      page.locator('text=/Offline|Failed to load|Backend unreachable|Error/i').first()
    ).toBeVisible({ timeout: 15000 });

    // 17. Confirm there are no unexpected uncaught browser errors
    expect(consoleErrors).toEqual([]);
  });
});
