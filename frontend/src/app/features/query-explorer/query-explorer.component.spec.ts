import { HttpErrorResponse } from '@angular/common/http';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { QueryExplorerComponent } from './query-explorer.component';
import { QueryExplorerParams, QueryExplorerView } from './query-explorer.models';
import { QueryExplorerService } from './query-explorer.service';

@Component({ standalone: true, template: 'Brand' })
class BrandStubComponent {}

@Component({ standalone: true, template: 'Audit' })
class AuditStubComponent {}

@Component({ standalone: true, template: 'Sign in' })
class LoginStubComponent {}

const auditId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const otherAuditId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

const emptyView: QueryExplorerView = {
  audit: null,
  audits: [],
  summary: null,
  items: [],
  pagination: { page: 1, page_size: 20, total: 0, pages: 0 },
};

const noQueriesView: QueryExplorerView = {
  audit: {
    id: auditId,
    brand_id: '11111111-1111-4111-8111-111111111111',
    brand_name: 'Northwind',
    created_at: '2026-09-23T12:00:00Z',
    completed_at: '2026-09-23T12:00:00Z',
    status: 'COMPLETED',
  },
  audits: [],
  summary: {
    total_queries: 0,
    responses: 0,
    failed: 0,
    mention_rate: null,
    citation_rate: null,
  },
  items: [],
  pagination: { page: 1, page_size: 20, total: 0, pages: 0 },
};

const responseText = 'Northwind appears first.\n<script>alert(1)</script>\nEND-OF-RESPONSE';

const withQueriesView: QueryExplorerView = {
  ...noQueriesView,
  audits: [
    noQueriesView.audit!,
    {
      id: otherAuditId,
      brand_id: '22222222-2222-4222-8222-222222222222',
      brand_name: 'Harbor',
      created_at: '2026-09-01T12:00:00Z',
      completed_at: '2026-09-01T12:00:00Z',
      status: 'COMPLETED',
    },
  ],
  summary: {
    total_queries: 3,
    responses: 2,
    failed: 1,
    mention_rate: 0.5,
    citation_rate: null,
  },
  items: [
    {
      query_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      query_text: 'Who is Northwind?',
      category: 'BRAND',
      created_at: '2026-09-23T12:05:00Z',
      has_response: true,
      response: {
        text: responseText,
        provider: 'mock',
        model: 'mock-model',
        brand_mentioned: true,
        brand_position: 1,
        citation_found: true,
        semantic_alignment: 0.72,
        latency_ms: 431,
      },
    },
    {
      query_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      query_text: 'Unanswered commercial query',
      category: 'COMMERCIAL',
      created_at: '2026-09-23T12:06:00Z',
      has_response: false,
      response: null,
    },
    {
      query_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
      query_text: 'Partial signals',
      category: 'PRODUCT',
      created_at: '2026-09-23T12:07:00Z',
      has_response: true,
      response: {
        text: 'No position was stored.',
        provider: 'mock',
        model: 'mock-model',
        brand_mentioned: null,
        brand_position: null,
        citation_found: null,
        semantic_alignment: null,
        latency_ms: null,
      },
    },
  ],
  pagination: { page: 1, page_size: 20, total: 3, pages: 1 },
};

const pagedView: QueryExplorerView = {
  ...withQueriesView,
  pagination: { page: 1, page_size: 10, total: 25, pages: 3 },
};

const filteredEmpty: QueryExplorerView = {
  ...withQueriesView,
  items: [],
  pagination: { page: 1, page_size: 20, total: 0, pages: 0 },
};

const queriesWithoutResponses: QueryExplorerView = {
  ...noQueriesView,
  summary: {
    total_queries: 2,
    responses: 0,
    failed: 2,
    mention_rate: null,
    citation_rate: null,
  },
  items: [
    {
      query_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      query_text: 'Generated only',
      category: 'INFORMATIONAL',
      created_at: '2026-09-23T12:06:00Z',
      has_response: false,
      response: null,
    },
  ],
  pagination: { page: 1, page_size: 20, total: 1, pages: 1 },
};

describe('QueryExplorerComponent', () => {
  let fixture: ComponentFixture<QueryExplorerComponent>;
  let explorer: jasmine.SpyObj<QueryExplorerService>;

  beforeEach(async () => {
    explorer = jasmine.createSpyObj('QueryExplorerService', ['getExplorerData']);

    await TestBed.configureTestingModule({
      imports: [QueryExplorerComponent],
      providers: [
        provideRouter([
          { path: 'query-explorer', component: QueryExplorerComponent },
          { path: 'brands', component: BrandStubComponent },
          { path: 'brands/new', component: BrandStubComponent },
          { path: 'audits/:id', component: AuditStubComponent },
          { path: 'login', component: LoginStubComponent },
        ]),
        { provide: QueryExplorerService, useValue: explorer },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(QueryExplorerComponent);
    fixture.detectChanges();
  }

  function lastParams(): QueryExplorerParams {
    return explorer.getExplorerData.calls.mostRecent().args[0] as QueryExplorerParams;
  }

  function selectValue(selector: string, value: string): void {
    const select = fixture.nativeElement.querySelector(selector) as HTMLSelectElement;
    select.value = value;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  it('shows a skeleton on the initial load', () => {
    explorer.getExplorerData.and.returnValue(new Subject<QueryExplorerView>());
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(fixture.nativeElement.querySelector('[aria-label="Loading query explorer"]')).not.toBeNull();
    expect(text).toContain('Loading query explorer');
    expect(text).toContain('Query Explorer');
    expect(text).not.toContain('Who is Northwind?');
  });

  it('shows an empty workspace when the user has no audits', () => {
    explorer.getExplorerData.and.returnValue(of(emptyView));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No audits to explore yet');
    expect(text).toContain('Add brand');
    expect(fixture.nativeElement.querySelector('a[href="/brands/new"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href="/brands"]')).not.toBeNull();
    expect(text).not.toContain('Mention rate');
  });

  it('shows the no-queries state with a link to the audit', () => {
    explorer.getExplorerData.and.returnValue(of(noQueriesView));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No AI queries yet.');
    expect(text).not.toContain('No queries match your filters.');
    const link = fixture.nativeElement.querySelector(`a[href="/audits/${auditId}"]`) as HTMLAnchorElement;
    expect(link?.textContent).toContain('View audit');
  });

  it('renders queries, responses, and null summary rates', () => {
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Who is Northwind?');
    expect(text).toContain('Responded');
    expect(text).toContain('50%');
    expect(text).toContain('2 / 3');

    const cards = Array.from(fixture.nativeElement.querySelectorAll('.stat')) as HTMLElement[];
    const citation = cards.find((card) => card.textContent?.includes('Citation rate'));
    expect(citation?.textContent).toContain('—');
    expect(citation?.textContent).not.toContain('0%');
  });

  it('shows failed queries without treating a missing response as an error', () => {
    explorer.getExplorerData.and.returnValue(of(queriesWithoutResponses));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Queries were generated, but no AI responses were recorded.');
    expect(text).toContain('Generated only');
    expect(text).toContain('No response');
    expect(text).toContain('—');
    expect(text).not.toContain('Unable to load Query Explorer');
  });

  it('filters by search, category, response, mention, and citation', () => {
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    create();

    const search = fixture.nativeElement.querySelector('input[type="search"]') as HTMLInputElement;
    search.value = '  northwind  ';
    search.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(lastParams().search).toBe('northwind');
    expect(lastParams().page).toBe(1);

    selectValue('.qe-filter--category', 'BRAND');
    expect(lastParams().category).toBe('BRAND');

    selectValue('.qe-filter--response', 'true');
    expect(lastParams().hasResponse).toBeTrue();

    selectValue('.qe-filter--mention', 'false');
    expect(lastParams().brandMentioned).toBeFalse();

    selectValue('.qe-filter--citation', 'true');
    expect(lastParams().citationFound).toBeTrue();
  });

  it('clears filters and asks for the unfiltered first page', () => {
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    create();
    selectValue('.qe-filter--category', 'PRODUCT');

    const clear = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Clear filters'),
    ) as HTMLButtonElement;
    clear.click();
    fixture.detectChanges();

    expect(lastParams().category).toBeNull();
    expect(lastParams().search).toBeNull();
    expect(lastParams().hasResponse).toBeNull();
    expect(lastParams().page).toBe(1);
    const select = fixture.nativeElement.querySelector('.qe-filter--category') as HTMLSelectElement;
    expect(select.value).toBe('');
  });

  it('shows a distinct empty state when filters match nothing', () => {
    explorer.getExplorerData.and.returnValues(of(withQueriesView), of(filteredEmpty));
    create();
    selectValue('.qe-filter--category', 'INDUSTRY');

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No queries match your filters.');
    expect(text).not.toContain('No AI queries yet.');
    expect(text).toContain('Clear filters');
  });

  it('pages on the server and keeps the current list while the next page loads', () => {
    const pending = new Subject<QueryExplorerView>();
    explorer.getExplorerData.and.returnValues(of(pagedView), pending.asObservable());
    create();

    const next = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Next'),
    ) as HTMLButtonElement;
    next.click();
    fixture.detectChanges();

    expect(lastParams().page).toBe(2);
    expect(fixture.nativeElement.textContent).toContain('Who is Northwind?');
    expect(fixture.nativeElement.textContent).toContain('Updating queries');
    expect(fixture.nativeElement.querySelector('[aria-label="Loading query explorer"]')).toBeNull();

    pending.next({ ...pagedView, pagination: { ...pagedView.pagination, page: 2 } });
    pending.complete();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Page 2 of 3');
  });

  it('expands a query and renders the full response as text', () => {
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    create();

    const toggle = fixture.nativeElement.querySelector('.qe-row__main') as HTMLButtonElement;
    toggle.click();
    fixture.detectChanges();

    const response = fixture.nativeElement.querySelector('.qe-response') as HTMLElement;
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(response.textContent).toContain('Northwind appears first.');
    expect(response.textContent).toContain('<script>alert(1)</script>');
    expect(response.textContent).toContain('END-OF-RESPONSE');
    expect(response.querySelector('script')).toBeNull();
    expect(response.innerHTML).toContain('&lt;script&gt;');
    expect(fixture.nativeElement.textContent).toContain('mock-model');
    expect(fixture.nativeElement.textContent).toContain('431 ms');
    expect(fixture.nativeElement.textContent).toContain('0.72');
  });

  it('renders unavailable response fields as an em dash', () => {
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    create();

    const toggles = fixture.nativeElement.querySelectorAll('.qe-row__main');
    (toggles[2] as HTMLButtonElement).click();
    fixture.detectChanges();

    const detail = fixture.nativeElement.querySelectorAll('.qe-detail')[0] as HTMLElement;
    expect(detail.textContent).toContain('Partial signals');
    expect(detail.textContent).toContain('Brand position');
    expect(detail.textContent).toContain('—');
    expect(detail.textContent).not.toContain('0 ms');
  });

  it('changes the audit from the selector and resets filters', () => {
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    create();
    selectValue('.qe-filter--category', 'BRAND');

    selectValue('.qe-audit__select', otherAuditId);

    expect(lastParams().auditId).toBe(otherAuditId);
    expect(lastParams().category).toBeNull();
    expect(lastParams().page).toBe(1);
    expect(navigate).toHaveBeenCalledWith(
      ['/query-explorer'],
      jasmine.objectContaining({ queryParams: { audit_id: otherAuditId } }),
    );
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Sep 23, 2026 — Northwind');
    expect(text).toContain('Sep 1, 2026 — Harbor');
  });

  it('shows an error and retries without exposing the backend message', () => {
    explorer.getExplorerData.and.returnValues(
      throwError(() => new HttpErrorResponse({ status: 500, error: { detail: 'Traceback: secret' } })),
      of(emptyView),
    );
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Unable to load Query Explorer');
    expect(text).toContain("We couldn't load Query Explorer. Please try again.");
    expect(text).not.toContain('Traceback');
    expect(text).not.toContain('secret');

    const retry = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Try again'),
    ) as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    expect(explorer.getExplorerData).toHaveBeenCalledTimes(2);
    expect(fixture.nativeElement.textContent).toContain('No audits to explore yet');
  });

  it('sends an expired session back to login', async () => {
    explorer.getExplorerData.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 401, statusText: 'Unauthorized' })),
    );
    create();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/login');
  });

  it('keeps the page readable in dark mode', () => {
    explorer.getExplorerData.and.returnValue(of(withQueriesView));
    document.documentElement.setAttribute('data-theme', 'dark');
    create();

    expect(fixture.nativeElement.querySelector('.qe-context')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.qe-table')).not.toBeNull();
    document.documentElement.setAttribute('data-theme', 'light');
  });
});
