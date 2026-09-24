import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { AuthUser } from '../../core/auth/auth.models';
import { DashboardComponent } from './dashboard.component';
import { DashboardOverview } from './dashboard.models';
import { DashboardService } from './dashboard.service';

@Component({ standalone: true, template: 'Brand' })
class BrandStubComponent {}

@Component({ standalone: true, template: 'Audit' })
class AuditStubComponent {}

@Component({ standalone: true, template: 'Sign in' })
class LoginStubComponent {}

const unavailableCard = {
  score: null,
  status: 'UNAVAILABLE' as const,
  explanation: 'Not calculated yet',
  audit_date: null,
  response_coverage: null,
  evidence_coverage: null,
};

const emptyOverview: DashboardOverview = {
  workspace: { brand_count: 0, audit_count: 0, completed_audit_count: 0 },
  selected_audit: null,
  scores: {
    overall: { score: null, status: 'UNAVAILABLE', explanation: 'Not available' },
    website: { ...unavailableCard },
    seo: { ...unavailableCard },
    ai_visibility: { ...unavailableCard },
    entity: { ...unavailableCard },
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

const brandsWithoutAudits: DashboardOverview = {
  ...emptyOverview,
  workspace: { brand_count: 1, audit_count: 0, completed_audit_count: 0 },
  brands: [{ id: '11111111-1111-4111-8111-111111111111', name: 'Northwind' }],
};

const fullOverview: DashboardOverview = {
  workspace: { brand_count: 2, audit_count: 4, completed_audit_count: 2 },
  selected_audit: {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    brand_id: '11111111-1111-4111-8111-111111111111',
    brand_name: 'Northwind',
    status: 'COMPLETED',
    created_at: '2026-09-22T15:00:00Z',
    completed_at: '2026-09-22T16:00:00Z',
    website_score_available: true,
    seo_score_available: true,
    ai_visibility_available: true,
    entity_available: false,
    overall_score_available: true,
    pages_crawled: 18,
    seo_findings: 11,
  },
  scores: {
    overall: {
      score: 68.4,
      status: 'PROVISIONAL',
      explanation:
        'Based on currently available website and SEO signals. AI Visibility and Entity Strength are not yet included in the overall score.',
    },
    website: {
      score: 72.1,
      status: 'AVAILABLE',
      explanation: 'Website health from the latest scored audit.',
      audit_date: '2026-09-22T16:00:00Z',
    },
    seo: {
      score: 69.2,
      status: 'AVAILABLE',
      explanation: 'SEO strength from stored findings and page signals.',
      audit_date: '2026-09-22T16:00:00Z',
    },
    ai_visibility: {
      score: 64.5,
      status: 'AVAILABLE',
      explanation: 'AI visibility from persisted query responses.',
      response_coverage: 0.89,
      audit_date: '2026-09-22T16:30:00Z',
    },
    entity: {
      score: null,
      status: 'UNAVAILABLE',
      explanation: 'Not calculated yet',
    },
  },
  snapshot: {
    pages_crawled: 18,
    seo_findings: 11,
    high_severity_findings: 3,
    ai_queries: 18,
    ai_successful_responses: 16,
    ai_response_coverage: 0.89,
    ai_mention_rate: 0.75,
    entity_pages_analyzed: null,
    pages_with_schema: 2,
    structured_identity_coverage: 0.1111,
    recommendations_total: 8,
    recommendations_high: 3,
    recommendations_medium: 4,
  },
  insights: [
    { text: '12 of 16 analyzed AI responses mentioned the brand.', source: 'AI_VISIBILITY' },
    { text: '3 high-severity SEO findings affect the site.', source: 'SEO_FINDINGS' },
    { text: '3 high-priority recommendations are available.', source: 'RECOMMENDATIONS' },
  ],
  recommendations: [
    {
      id: 'r1',
      title: 'Fix meta descriptions',
      category: 'SEO',
      priority: 'HIGH',
      impact_score: 90,
      effort_score: 20,
    },
    {
      id: 'r2',
      title: 'Improve AI mentions',
      category: 'AI_VISIBILITY',
      priority: 'HIGH',
      impact_score: 80,
      effort_score: 40,
    },
  ],
  freshness: {
    last_website_crawl: '2026-09-22T15:10:00Z',
    last_seo_analysis: '2026-09-22T15:20:00Z',
    last_ai_analysis: '2026-09-22T16:30:00Z',
    last_recommendations_calculation: '2026-09-22T16:40:00Z',
  },
  brands: [
    { id: '11111111-1111-4111-8111-111111111111', name: 'Northwind' },
    { id: '22222222-2222-4222-8222-222222222222', name: 'Harbor' },
  ],
  selection_rule: 'latest completed',
};

const partialOverview: DashboardOverview = {
  ...fullOverview,
  scores: {
    ...fullOverview.scores,
    ai_visibility: { ...unavailableCard },
    entity: { ...unavailableCard },
    overall: {
      score: 70,
      status: 'PROVISIONAL',
      explanation:
        'Based on currently available website and SEO signals. AI Visibility and Entity Strength are not yet included in the overall score.',
    },
  },
  snapshot: {
    ...fullOverview.snapshot,
    ai_queries: null,
    ai_successful_responses: null,
    ai_response_coverage: null,
    ai_mention_rate: null,
  },
  insights: [{ text: '3 high-severity SEO findings affect the site.', source: 'SEO_FINDINGS' }],
  recommendations: [],
};

describe('DashboardComponent', () => {
  let fixture: ComponentFixture<DashboardComponent>;
  let dashboard: jasmine.SpyObj<DashboardService>;
  let user: ReturnType<typeof signal<AuthUser | null>>;

  beforeEach(async () => {
    dashboard = jasmine.createSpyObj('DashboardService', ['getOverview']);
    user = signal<AuthUser | null>({
      id: '1',
      email: 'ada@example.com',
      full_name: 'Ada Lovelace',
    });

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([
          { path: 'dashboard', component: DashboardComponent },
          { path: 'brands', component: BrandStubComponent },
          { path: 'brands/new', component: BrandStubComponent },
          { path: 'brands/:id', component: BrandStubComponent },
          { path: 'audits/:id', component: AuditStubComponent },
          { path: 'login', component: LoginStubComponent },
        ]),
        { provide: DashboardService, useValue: dashboard },
        { provide: AuthService, useValue: { currentUser: user } },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
  }

  it('shows a skeleton without metrics while the overview is loading', () => {
    dashboard.getOverview.and.returnValue(new Subject<DashboardOverview>());
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(fixture.nativeElement.querySelector('[aria-label="Loading dashboard"]')).not.toBeNull();
    expect(text).toContain('Loading dashboard');
    expect(text).toContain('Good morning, Ada');
    expect(text).not.toContain('Website Health');
    expect(text).not.toContain('Sample data');
    expect(text).not.toContain('Lumen');
  });

  it('renders full intelligence dashboard data', () => {
    dashboard.getOverview.and.returnValue(of(fullOverview));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Overall Intelligence');
    expect(text).toContain('68.4');
    expect(text).toContain('Provisional');
    expect(text).toContain('Website Health');
    expect(text).toContain('72.1');
    expect(text).toContain('SEO');
    expect(text).toContain('69.2');
    expect(text).toContain('AI Visibility');
    expect(text).toContain('64.5');
    expect(text).toContain('Entity Strength');
    expect(text).toContain('Not calculated yet');
    expect(text).toContain('12 of 16 analyzed AI responses mentioned the brand.');
    expect(text).toContain('Fix meta descriptions');
    expect(text).toContain('View all recommendations');
    expect(text).toContain('View audit');
    expect(text).toContain('Pages crawled');
    expect(text).toContain('18');
    expect(text).not.toContain('Sample data');
    expect(text).not.toContain('42%');

    const viewAudit = fixture.nativeElement.querySelector(
      'a[href="/audits/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]',
    ) as HTMLAnchorElement;
    expect(viewAudit).not.toBeNull();
  });

  it('shows empty workspace onboarding without fake scores', () => {
    dashboard.getOverview.and.returnValue(of(emptyOverview));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No brands yet.');
    expect(text).toContain('Add brand');
    expect(text).not.toContain('Website Health');
    expect(text).not.toContain('0 / 100');
    expect(fixture.nativeElement.querySelector('a[href="/brands/new"]')?.textContent).toContain(
      'Add brand',
    );
  });

  it('shows brands without audits CTA', () => {
    dashboard.getOverview.and.returnValue(of(brandsWithoutAudits));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('You have 1 brand and no audits yet');
    expect(text).toContain('Open brands');
    expect(text).not.toContain('Website Health');
  });

  it('keeps partial layers as em dash and provisional overall', () => {
    dashboard.getOverview.and.returnValue(of(partialOverview));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Provisional');
    expect(text).toContain('Website Health');
    expect(text).toContain('AI Visibility');
    expect(text).toContain('—');
    expect(text).toContain('Not calculated yet');
    expect(text).toContain('No recommendations yet.');
    expect(text).not.toContain('0 / 100');
  });

  it('shows an error and retries without exposing the backend message', () => {
    dashboard.getOverview.and.returnValues(
      throwError(() => new HttpErrorResponse({ status: 500, error: { detail: 'Traceback: secret' } })),
      of(emptyOverview),
    );
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Unable to load dashboard');
    expect(text).toContain("We couldn't load your dashboard. Please try again.");
    expect(text).not.toContain('Traceback');
    expect(text).not.toContain('secret');

    const retry = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Try again'),
    ) as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    expect(dashboard.getOverview).toHaveBeenCalledTimes(2);
    expect(fixture.nativeElement.textContent).toContain('No brands yet.');
  });

  it('sends an expired session back to login', async () => {
    dashboard.getOverview.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 401, statusText: 'Unauthorized' })),
    );
    create();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/login');
  });

  it('refreshes and keeps current metrics while the next request is in flight', () => {
    const pending = new Subject<DashboardOverview>();
    dashboard.getOverview.and.returnValues(of(emptyOverview), pending.asObservable());
    create();

    expect(fixture.nativeElement.textContent).toContain('No brands yet.');

    const refresh = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Refresh'),
    ) as HTMLButtonElement;
    refresh.click();
    fixture.detectChanges();

    expect(dashboard.getOverview).toHaveBeenCalledTimes(2);
    expect(fixture.nativeElement.textContent).toContain('No brands yet.');

    pending.next(brandsWithoutAudits);
    pending.complete();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('You have 1 brand and no audits yet');
  });

  it('greets a user without a full name and offers a brand selector for multiple brands', () => {
    user.set({ id: '1', email: 'ada@example.com', full_name: null });
    dashboard.getOverview.and.returnValue(of(fullOverview));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Good morning');
    expect(text).not.toContain('Good morning,');
    expect(text).not.toContain('ada@example.com');

    const select = fixture.nativeElement.querySelector('.dashboard__brand-select') as HTMLSelectElement;
    expect(select).not.toBeNull();
    expect(select.options.length).toBe(3);
    expect(select.options[0].textContent).toContain('All Brands');
  });

  it('supports dark theme tokens on score cards', () => {
    dashboard.getOverview.and.returnValue(of(fullOverview));
    document.documentElement.setAttribute('data-theme', 'dark');
    create();

    expect(fixture.nativeElement.querySelector('.dash-overall')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.dash-score-card')).not.toBeNull();
    document.documentElement.setAttribute('data-theme', 'light');
  });
});
