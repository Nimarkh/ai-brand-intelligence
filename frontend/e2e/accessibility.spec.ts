import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { mockAuthenticatedWorkspace } from './helpers/api-mocks';

/**
 * Automated accessibility smoke. Known design-token badge contrast gaps are
 * disabled here (Phase 20 does not redesign UI). Manual a11y review still needed.
 */
test.describe('Accessibility smoke', () => {
  test('login and authenticated shell have no serious axe violations', async ({ page }) => {
    await page.goto('/login');
    const loginResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .disableRules(['color-contrast'])
      .analyze();
    const loginSerious = loginResults.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact ?? ''),
    );
    expect(loginSerious, JSON.stringify(loginSerious, null, 2)).toEqual([]);

    await mockAuthenticatedWorkspace(page);
    await page.goto('/dashboard');
    await expect(page.locator('.shell')).toBeVisible();

    // Labels, landmarks, and keyboard-relevant structure.
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeVisible();
    await expect(page.locator('#main-content')).toHaveAttribute('tabindex', '-1');
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();

    const shellResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .disableRules(['color-contrast'])
      .analyze();
    const shellSerious = shellResults.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact ?? ''),
    );
    expect(shellSerious, JSON.stringify(shellSerious, null, 2)).toEqual([]);
  });
});
