import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of } from 'rxjs';

import { routes } from '../../app.routes';
import { AuthService } from '../../core/auth/auth.service';
import { AuthUser } from '../../core/auth/auth.models';
import { THEME_STORAGE_KEY } from '../../core/theme/theme.service';
import { DashboardOverview } from '../../features/dashboard/dashboard.models';
import { DashboardService } from '../../features/dashboard/dashboard.service';
import { SIDEBAR_STORAGE_KEY } from '../sidebar/sidebar.service';

const emptyDashboard: DashboardOverview = {
  workspace: { brand_count: 0, audit_count: 0, completed_audit_count: 0 },
  selected_audit: null,
  scores: {
    overall: { score: null, status: 'UNAVAILABLE', explanation: 'Not available' },
    website: { score: null, status: 'UNAVAILABLE', explanation: 'Not calculated yet' },
    seo: { score: null, status: 'UNAVAILABLE', explanation: 'Not calculated yet' },
    ai_visibility: { score: null, status: 'UNAVAILABLE', explanation: 'Not calculated yet' },
    entity: { score: null, status: 'UNAVAILABLE', explanation: 'Not calculated yet' },
  },
  snapshot: {
    pages_crawled: null,
    seo_findings: null,
    high_severity_findings: null,
    ai_queries: null,
    ai_successful_responses: null,
    ai_response_coverage: null,
    ai_mention_rate: null,
    entity_pages_analyzed: null,
    pages_with_schema: null,
    structured_identity_coverage: null,
    recommendations_total: null,
    recommendations_high: null,
    recommendations_medium: null,
  },
  insights: [],
  recommendations: [],
  freshness: {
    last_website_crawl: null,
    last_seo_analysis: null,
    last_ai_analysis: null,
    last_recommendations_calculation: null,
  },
  brands: [],
  selection_rule: 'latest completed',
};

const user: AuthUser = {
  id: '1',
  email: 'ada@example.com',
  full_name: 'Ada Lovelace',
};

describe('ShellComponent', () => {
  let logout: jasmine.Spy;

  beforeEach(() => {
    localStorage.removeItem(THEME_STORAGE_KEY);
    localStorage.removeItem(SIDEBAR_STORAGE_KEY);
    document.documentElement.setAttribute('data-theme', 'light');

    logout = jasmine.createSpy('logout').and.returnValue(of({ status: 'ok' }));
    const auth = {
      currentUser: signal(user),
      ensureSession: () => of(user),
      logout,
    };

    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        { provide: AuthService, useValue: auth },
        { provide: DashboardService, useValue: { getOverview: () => of(emptyDashboard) } },
      ],
    });
  });

  afterEach(() => {
    localStorage.removeItem(THEME_STORAGE_KEY);
    localStorage.removeItem(SIDEBAR_STORAGE_KEY);
    document.documentElement.setAttribute('data-theme', 'light');
  });

  it('renders the sidebar, topbar, and dashboard', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    const root = harness.fixture.nativeElement as HTMLElement;

    expect(root.querySelector('app-sidebar')).not.toBeNull();
    expect(root.querySelector('.topbar')).not.toBeNull();
    expect(root.textContent).toContain('AI Brand Intelligence');
    expect(root.textContent).toContain('Ada Lovelace');
    expect(root.textContent).toContain('Good morning, Ada');
    expect(root.textContent).toContain('No brands yet.');
    expect(root.textContent).toContain('Add brand');
    expect(root.textContent).toContain('AI Visibility');
    expect(root.textContent).not.toContain('Sample data');
    expect(root.textContent).not.toContain('not live measurements');
    expect(root.querySelector('a.is-active')?.textContent).toContain('Dashboard');
  });

  it('marks the active navigation item', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');

    await harness.navigateByUrl('/settings');

    const active = (harness.fixture.nativeElement as HTMLElement).querySelector('a.is-active');
    expect(active?.textContent).toContain('Settings');
    expect(active?.getAttribute('href')).toBe('/settings');
  });

  it('collapses the sidebar and remembers the preference', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    const root = harness.fixture.nativeElement as HTMLElement;
    const collapse = root.querySelector('[aria-label="Collapse sidebar"]') as HTMLButtonElement;

    collapse.click();
    harness.fixture.detectChanges();

    expect(root.querySelector('.sidebar')?.classList.contains('sidebar--collapsed')).toBeTrue();
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('true');
    expect(root.querySelector('[aria-label="Expand sidebar"]')).not.toBeNull();
  });

  it('opens and closes mobile navigation', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    const root = harness.fixture.nativeElement as HTMLElement;
    const menu = root.querySelector('[aria-label="Open navigation"]') as HTMLButtonElement;

    menu.click();
    harness.fixture.detectChanges();

    expect(root.querySelector('.shell')?.classList.contains('shell--drawer-open')).toBeTrue();
    expect(root.querySelector('.sidebar')?.classList.contains('sidebar--open')).toBeTrue();

    const close = root.querySelector('[aria-label="Close navigation"]') as HTMLButtonElement;
    close.click();
    harness.fixture.detectChanges();

    expect(root.querySelector('.shell')?.classList.contains('shell--drawer-open')).toBeFalse();
  });

  it('signs out from the profile menu and returns to login', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    const root = harness.fixture.nativeElement as HTMLElement;

    (root.querySelector('[aria-label="Account menu"]') as HTMLButtonElement).click();
    harness.fixture.detectChanges();

    expect(root.textContent).toContain('ada@example.com');

    const signOut = Array.from(root.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Sign out'),
    );
    signOut?.click();
    await harness.fixture.whenStable();

    expect(logout).toHaveBeenCalled();
    expect(TestBed.inject(Router).url).toBe('/login');
  });

  it('toggles the theme from the topbar', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    const root = harness.fixture.nativeElement as HTMLElement;

    (root.querySelector('[aria-label="Switch to dark mode"]') as HTMLButtonElement).click();
    harness.fixture.detectChanges();

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });
});
