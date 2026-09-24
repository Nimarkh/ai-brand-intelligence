import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AIVisibilityResponse } from '../audits/ai-visibility.models';
import { AiVisibilityService } from '../audits/ai-visibility.service';
import { IntelligenceAuditList } from '../intelligence-chat/intelligence.models';
import { IntelligenceService } from '../intelligence-chat/intelligence.service';
import { QueryExplorerView } from '../query-explorer/query-explorer.models';
import { QueryExplorerService } from '../query-explorer/query-explorer.service';
import { AiVisibilityComponent } from './ai-visibility.component';

const auditId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

const catalog: IntelligenceAuditList = {
  audits: [
    {
      id: auditId,
      brand_id: '11111111-1111-4111-8111-111111111111',
      brand_name: 'Northwind',
      status: 'COMPLETED',
      created_at: '2026-09-23T12:00:00Z',
      completed_at: '2026-09-23T12:30:00Z',
    },
  ],
  selected_audit_id: auditId,
};

const visibility: AIVisibilityResponse = {
  audit_id: auditId,
  status: 'PROVISIONAL',
  overall_score: 55,
  metrics: {
    mention_rate: 0.5,
    citation_rate: null,
    average_position: 2,
    position_score: 70,
    semantic_alignment: 0.42,
    semantic_score: 42,
  },
  components: { mention: 50, citation: null, position: 70, semantic: 42 },
  total_queries: 2,
  successful_responses: 1,
  failed_responses: 1,
  response_coverage: 0.5,
  note: 'AI Visibility is provisional because some AI queries have no response.',
};

const explorer: QueryExplorerView = {
  audit: null,
  audits: [],
  summary: null,
  items: [
    {
      query_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      query_text: 'Who is Northwind?',
      category: 'BRAND',
      created_at: '2026-09-23T12:05:00Z',
      has_response: true,
      response: {
        text: 'Northwind is first.',
        provider: 'mock',
        model: 'mock',
        brand_mentioned: true,
        brand_position: 1,
        citation_found: false,
        semantic_alignment: 0.42,
        latency_ms: 10,
      },
    },
  ],
  pagination: { page: 1, page_size: 10, total: 1, pages: 1 },
};

describe('AiVisibilityComponent', () => {
  let fixture: ComponentFixture<AiVisibilityComponent>;
  let intelligence: jasmine.SpyObj<IntelligenceService>;
  let visibilityApi: jasmine.SpyObj<AiVisibilityService>;
  let explorerApi: jasmine.SpyObj<QueryExplorerService>;

  beforeEach(async () => {
    intelligence = jasmine.createSpyObj('IntelligenceService', ['getAudits']);
    visibilityApi = jasmine.createSpyObj('AiVisibilityService', ['getVisibility']);
    explorerApi = jasmine.createSpyObj('QueryExplorerService', ['getExplorerData']);
    await TestBed.configureTestingModule({
      imports: [AiVisibilityComponent],
      providers: [
        provideRouter([{ path: 'ai-visibility', component: AiVisibilityComponent }]),
        { provide: IntelligenceService, useValue: intelligence },
        { provide: AiVisibilityService, useValue: visibilityApi },
        { provide: QueryExplorerService, useValue: explorerApi },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(AiVisibilityComponent);
    fixture.detectChanges();
  }

  it('renders persisted metrics, provisional status, and query evidence', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    visibilityApi.getVisibility.and.returnValue(of(visibility));
    explorerApi.getExplorerData.and.returnValue(of(explorer));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Mention Rate');
    expect(text).toContain('50.0%');
    expect(text).toContain('Citation Rate');
    expect(text).toContain('Citation Rate—');
    expect(text).toContain('Position');
    expect(text).toContain('Semantic Match');
    expect(text).toContain('Provisional');
    expect(text).toContain('Who is Northwind?');
    expect(text).toContain('heuristic');
    expect(text).toContain('not a search-engine ranking');
    expect(text).toContain('lexical');
    const link = fixture.nativeElement.querySelector('a[href="/query-explorer?audit_id=' + auditId + '"]');
    expect(link).not.toBeNull();
  });

  it('shows an empty state when the audit has no AI queries', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    visibilityApi.getVisibility.and.returnValue(
      of({
        ...visibility,
        status: 'UNAVAILABLE',
        overall_score: null,
        metrics: {
          mention_rate: null,
          citation_rate: null,
          average_position: null,
          position_score: null,
          semantic_alignment: null,
          semantic_score: null,
        },
        total_queries: 0,
        successful_responses: 0,
        failed_responses: 0,
        response_coverage: null,
        note: null,
      }),
    );
    explorerApi.getExplorerData.and.returnValue(
      of({ ...explorer, items: [], pagination: { page: 1, page_size: 10, total: 0, pages: 0 } }),
    );
    create();

    expect(fixture.nativeElement.textContent).toContain('No AI analysis yet');
    expect(fixture.nativeElement.textContent).not.toContain('0 / 100');
  });

  it('shows an empty state when the user has no audits', () => {
    intelligence.getAudits.and.returnValue(of({ audits: [], selected_audit_id: null }));
    create();

    expect(fixture.nativeElement.textContent).toContain('No audits to review yet');
    expect(visibilityApi.getVisibility).not.toHaveBeenCalled();
  });

  it('shows an error state when the catalog fails', () => {
    intelligence.getAudits.and.returnValue(throwError(() => new HttpErrorResponse({ status: 503 })));
    create();

    expect(fixture.nativeElement.textContent).toContain('Unable to load AI Visibility');
    expect(fixture.nativeElement.textContent).toContain('Something went wrong. Please try again.');
  });
});
