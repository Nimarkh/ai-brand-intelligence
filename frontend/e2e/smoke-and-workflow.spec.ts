import { expect, test } from '@playwright/test';

import { loginViaUi, mockAuthenticatedWorkspace, mockCoreWorkflow } from './helpers/api-mocks';

test.describe('Smoke', () => {
  test('login, dashboard, brands, and settings load', async ({ page }) => {
    await mockAuthenticatedWorkspace(page);
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible();
    await expect(page.locator('.shell')).toBeVisible();

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Brands' }).click();
    await expect(page).toHaveURL(/\/brands/);
    await expect(page.getByRole('heading', { name: 'Brands', exact: true })).toBeVisible();
    await expect(page.getByText('Fixture Brand')).toBeVisible();

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Settings' }).click();
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  });

  test('login form signs in against mocked API', async ({ page }) => {
    await mockCoreWorkflow(page);
    await loginViaUi(page);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator('.shell')).toBeVisible();
  });
});

test.describe('Core workflow', () => {
  test('brand → audit pipeline → intelligence → report download', async ({ page }) => {
    await mockCoreWorkflow(page);
    await loginViaUi(page);

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Brands' }).click();
    await page.getByRole('link', { name: '+ Add brand' }).first().click();
    await expect(page).toHaveURL(/\/brands\/new/);

    await page.getByLabel('Brand name *').fill('Fixture Brand');
    await page.getByLabel('Website URL *').fill('https://fixture.test');
    await page.getByLabel('Industry *').fill('Outdoor');
    await page.getByLabel('Country *').fill('United States');
    await page.getByLabel('Target market *').fill('North America');
    await page.getByLabel('Description').fill('Durable outdoor equipment for independent retailers.');
    await page.getByRole('button', { name: 'Create brand' }).click();

    await expect(page).toHaveURL(/\/brands\/22222222-2222-4222-8222-222222222222/);
    await page.getByRole('button', { name: 'Start website crawl' }).click();
    await expect(page.getByRole('link', { name: 'Open audit / Analyze SEO' })).toBeVisible();

    await page.getByRole('link', { name: 'Open audit / Analyze SEO' }).click();
    await expect(page).toHaveURL(/\/audits\/33333333-3333-4333-8333-333333333333/);

    await page.getByRole('button', { name: 'Analyze SEO' }).click();
    await page.getByRole('button', { name: 'Calculate score' }).click();
    await page.getByRole('button', { name: 'Run AI Analysis' }).click();
    await page.getByRole('button', { name: 'Calculate AI Visibility' }).click();
    await page.getByRole('button', { name: 'Calculate Entity' }).click();
    await page.getByRole('button', { name: 'Calculate Recommendations' }).click();

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Query Explorer' }).click();
    await expect(page.getByText('Who is Fixture Brand?')).toBeVisible();

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Ask Intelligence' }).click();
    await page.locator('#ask-question').fill('What are the main SEO issues?');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.getByText(/missing meta description/i).first()).toBeVisible();

    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Reports' }).click();
    await page.getByRole('button', { name: 'Generate Report' }).first().click();
    await expect(page.getByRole('dialog', { name: 'Select audit' })).toBeVisible();
    await page.getByRole('dialog', { name: 'Select audit' }).getByRole('button', { name: 'Generate Report' }).click();
    await expect(page.getByRole('button', { name: 'Download' }).first()).toBeVisible();

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download' }).first().click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/audit-intelligence-report\.pdf$/i);
  });
});

test.describe('Responsive', () => {
  for (const width of [375, 1280] as const) {
    test(`shell and query explorer at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await mockAuthenticatedWorkspace(page);
      await page.goto('/dashboard');
      await expect(page.locator('.shell')).toBeVisible();
      await expect(page.locator('#main-content')).toBeVisible();
      if (width <= 500) {
        await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible();
      } else {
        await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
      }

      await page.goto('/query-explorer');
      await expect(page.getByRole('heading', { name: 'Query Explorer', exact: true })).toBeVisible();
    });
  }
});
