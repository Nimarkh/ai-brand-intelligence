import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, Subject, throwError } from 'rxjs';

import { Brand } from '../brands/brand.models';
import { BrandService } from '../brands/brand.service';
import { BrandsComponent } from '../brands/brands.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import { AiQueryService } from './ai-query.service';
import { AiQueryListResponse, AiQueryRunResponse } from './ai-query.models';
import { AiVisibilityService } from './ai-visibility.service';
import { AIVisibilityResponse } from './ai-visibility.models';
import { EntityService } from './entity.service';
import { EntityStrengthResponse } from './entity.models';
import { RecommendationService } from './recommendation.service';
import {
  RecommendationListResponse,
  RecommendationRunResponse,
} from './recommendation.models';
import { AuditDetailComponent } from './audit-detail.component';
import { AuditScoreResponse, AuditSummary, SeoFindingListResponse } from './audit.models';
import { AuditService } from './audit.service';

const brand: Brand = {
  id: '11111111-1111-4111-8111-111111111111',
  name: 'Northwind',
  website_url: 'https://northwind.example',
  industry: 'Retail',
  country: 'United States',
  target_market: 'North America',
  description: 'Outdoor goods',
  created_at: '2026-03-01T12:00:00Z',
  updated_at: '2026-03-01T12:00:00Z',
};

const audit: AuditSummary = {
  id: '22222222-2222-4222-8222-222222222222',
  brand_id: brand.id,
  status: 'COMPLETED',
  pages_crawled: 4,
  overall_score: null,
  website_score: null,
  seo_score: null,
  ai_visibility_score: null,
  entity_score: null,
  semantic_score: null,
  started_at: '2026-03-02T12:00:00Z',
  completed_at: '2026-03-02T12:01:00Z',
  created_at: '2026-03-02T12:00:00Z',
};

const emptyFindings: SeoFindingListResponse = { items: [], total: 0 };

const emptyAiQueries: AiQueryListResponse = { items: [], total: 0 };

const unavailableVisibility: AIVisibilityResponse = {
  audit_id: audit.id,
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
  components: { mention: null, citation: null, position: null, semantic: null },
  total_queries: 0,
  successful_responses: 0,
  failed_responses: 0,
  response_coverage: null,
  note: 'AI Visibility has not been calculated yet for this audit.',
};

const unavailableEntity: EntityStrengthResponse = {
  audit_id: audit.id,
  status: 'UNAVAILABLE',
  overall_score: null,
  metrics: {
    title_presence_rate: null,
    meta_presence_rate: null,
    title_consistency: null,
    canonical_consistency: null,
    schema_consistency: null,
    entity_schema_coverage: null,
    schema_quality: null,
    ai_mention_rate: null,
    ai_position_score: null,
  },
  components: {
    presence: null,
    consistency: null,
    structured_identity: null,
    ai_recognition: null,
  },
  component_details: [],
  evidence: {
    analyzable_pages: 0,
    pages_with_brand_in_title: 0,
    pages_with_brand_in_meta: 0,
    pages_with_canonical: 0,
    pages_with_same_origin_canonical: 0,
    pages_with_schema: 0,
    pages_with_entity_schema: 0,
    successful_ai_responses: 0,
    responses_mentioning_brand: 0,
    average_mention_position: null,
    brand_name: 'Northwind',
    normalized_brand_name: 'northwind',
    origin: null,
  },
  notes: [
    'This score evaluates signals found on the audited website and analyzed AI responses. It does not verify Google Knowledge Graph, Wikidata, Wikipedia, or third-party entity databases.',
  ],
};


const emptyRecommendations: RecommendationListResponse = { items: [], total: 0 };

const unavailableScore: AuditScoreResponse = {
  audit_id: audit.id,
  status: 'UNAVAILABLE',
  website_health: { score: null, status: 'UNAVAILABLE' },
  seo: { score: null, status: 'UNAVAILABLE' },
  overall: { score: null, status: 'UNAVAILABLE' },
  components: [],
  findings_count: 0,
  affected_pages: 0,
  analyzable_pages: 4,
  ai_visibility: { score: null, status: 'UNAVAILABLE' },
  entity_strength: { score: null, status: 'UNAVAILABLE' },
  note: 'Score has not been calculated yet.',
};

const scored: AuditScoreResponse = {
  audit_id: audit.id,
  status: 'PROVISIONAL',
  website_health: { score: 92.5, status: 'AVAILABLE' },
  seo: { score: 85, status: 'AVAILABLE' },
  overall: { score: 89.17, status: 'PROVISIONAL' },
  components: [
    {
      name: 'technical',
      score: 100,
      status: 'AVAILABLE',
      findings_count: 0,
      affected_pages: 0,
      top_penalty_categories: [],
    },
    {
      name: 'seo',
      score: 85,
      status: 'AVAILABLE',
      findings_count: 1,
      affected_pages: 1,
      top_penalty_categories: ['TITLE'],
    },
    {
      name: 'content',
      score: 100,
      status: 'AVAILABLE',
      findings_count: 0,
      affected_pages: 0,
      top_penalty_categories: [],
    },
    {
      name: 'structured_data',
      score: 100,
      status: 'AVAILABLE',
      findings_count: 0,
      affected_pages: 0,
      top_penalty_categories: [],
    },
  ],
  findings_count: 1,
  affected_pages: 1,
  analyzable_pages: 4,
  ai_visibility: { score: null, status: 'UNAVAILABLE' },
  entity_strength: { score: null, status: 'UNAVAILABLE' },
  note: 'Overall score is provisional.',
};

describe('AuditDetailComponent', () => {
  let audits: jasmine.SpyObj<AuditService>;
  let brands: jasmine.SpyObj<BrandService>;
  let aiQueries: jasmine.SpyObj<AiQueryService>;
  let visibilityApi: jasmine.SpyObj<AiVisibilityService>;
  let entityApi: jasmine.SpyObj<EntityService>;
  let recommendationsApi: jasmine.SpyObj<RecommendationService>;

  beforeEach(() => {
    audits = jasmine.createSpyObj('AuditService', [
      'getAudit',
      'analyzeSeo',
      'listSeoFindings',
      'listAudits',
      'createAudit',
      'crawl',
      'getScore',
      'calculateScore',
    ]);
    brands = jasmine.createSpyObj('BrandService', ['getBrand']);
    aiQueries = jasmine.createSpyObj('AiQueryService', ['run', 'list', 'get']);
    visibilityApi = jasmine.createSpyObj('AiVisibilityService', ['calculateVisibility', 'getVisibility']);
    entityApi = jasmine.createSpyObj('EntityService', ['calculateEntity', 'getEntity']);
    recommendationsApi = jasmine.createSpyObj('RecommendationService', [
      'calculateRecommendations',
      'getRecommendations',
    ]);
    audits.getAudit.and.returnValue(of(audit));
    audits.listSeoFindings.and.returnValue(of(emptyFindings));
    audits.getScore.and.returnValue(of(unavailableScore));
    aiQueries.list.and.returnValue(of(emptyAiQueries));
    visibilityApi.getVisibility.and.returnValue(of(unavailableVisibility));
    entityApi.getEntity.and.returnValue(of(unavailableEntity));
    recommendationsApi.getRecommendations.and.returnValue(of(emptyRecommendations));
    brands.getBrand.and.returnValue(of(brand));

    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'audits/:id', component: AuditDetailComponent },
          { path: 'brands', component: BrandsComponent },
          { path: 'login', component: BrandsComponent },
        ]),
        { provide: AuditService, useValue: audits },
        { provide: BrandService, useValue: brands },
        { provide: AiQueryService, useValue: aiQueries },
        { provide: AiVisibilityService, useValue: visibilityApi },
        { provide: EntityService, useValue: entityApi },
        { provide: RecommendationService, useValue: recommendationsApi },
        { provide: ToastService, useValue: { show: jasmine.createSpy('show'), toasts: signal([]) } },
      ],
    });
  });

  it('shows score unavailable state', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Score not calculated');
    expect(text).toContain('Calculate score');
    expect(text).toContain('Analyze SEO');
    expect(text).toContain('AI Query Analysis');
    expect(text).toContain('AI Visibility');
    expect(text).toContain('AI Visibility not available');
    expect(text).toContain('Calculate AI Visibility');
    expect(text).toContain('Entity Intelligence');
    expect(text).toContain('Calculate Entity');
    expect(text).toContain('does not verify Google Knowledge Graph');
    expect(text).toContain('Recommendations');
    expect(text).toContain('Calculate Recommendations');
    expect(text).toContain('No recommendations yet');
    expect(text).toContain('Based on analyzed evidence');
    expect(text).toContain('No AI queries yet.');
    expect(text).toContain('Run AI Analysis');
    expect(text).toContain('not search ranking');
    expect(text).not.toContain('AI Visibility: 0');
  });

  it('shows not-found without implying another owner', async () => {
    audits.getAudit.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found' })),
    );
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Audit not found');
    expect(text).not.toContain('another user');
  });

  it('calculates and displays provisional scores', async () => {
    const calculated = new Subject<AuditScoreResponse>();
    audits.calculateScore.and.returnValue(calculated.asObservable());
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const button = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('Calculate score'),
    ) as HTMLButtonElement;
    button.click();
    harness.detectChanges();
    expect(component.scoring()).toBeTrue();
    expect(harness.fixture.nativeElement.textContent).toContain('Calculating score');

    calculated.next(scored);
    calculated.complete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(audits.calculateScore).toHaveBeenCalledWith(audit.id);
    expect(text).toContain('Website Health');
    expect(text).toContain('92.5 / 100');
    expect(text).toContain('85 / 100');
    expect(text).toContain('Provisional');
    expect(text).toContain('1 finding across 1 page');
    expect(text).toContain('Technical');
    expect(text).toContain('Entity Strength: see the Entity Intelligence section');
    expect(text).not.toContain('AI Visibility: 0');
  });

  it('runs SEO analysis and shows finding count', async () => {
    const analyzed = new Subject<{ audit_id: string; findings_count: number; status: string }>();
    audits.analyzeSeo.and.returnValue(analyzed.asObservable());
    audits.listSeoFindings.and.returnValues(
      of(emptyFindings),
      of({
        total: 2,
        items: [
          {
            id: '33333333-3333-4333-8333-333333333333',
            audit_id: audit.id,
            page_id: '44444444-4444-4444-8444-444444444444',
            category: 'TITLE',
            severity: 'HIGH',
            title: 'Missing page title',
            description: 'This page has no HTML title.',
            recommendation: 'Add a descriptive title.',
            created_at: '2026-03-02T12:02:00Z',
            page: {
              id: '44444444-4444-4444-8444-444444444444',
              url: 'https://northwind.example/products',
              status_code: 200,
            },
          },
          {
            id: '55555555-5555-4555-8555-555555555555',
            audit_id: audit.id,
            page_id: null,
            category: 'META_DESCRIPTION',
            severity: 'MEDIUM',
            title: 'Missing meta description',
            description: 'No meta description.',
            recommendation: 'Add a meta description.',
            created_at: '2026-03-02T12:02:00Z',
            page: null,
          },
        ],
      }),
    );

    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const button = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('Analyze SEO'),
    ) as HTMLButtonElement;
    button.click();
    harness.detectChanges();

    analyzed.next({ audit_id: audit.id, findings_count: 2, status: 'COMPLETED' });
    analyzed.complete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    expect(audits.analyzeSeo).toHaveBeenCalledWith(audit.id);
    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('SEO analysis completed — 2 findings.');
    expect(text).toContain('Missing page title');
  });

  it('redirects to login on unauthorized score', async () => {
    audits.calculateScore.and.returnValue(throwError(() => new HttpErrorResponse({ status: 401 })));
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    component.calculateScore();
    await harness.fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/login');
  });

  it('runs AI analysis and shows partial failure summary', async () => {
    const run$ = new Subject<AiQueryRunResponse>();
    aiQueries.run.and.returnValue(run$.asObservable());
    aiQueries.list.and.returnValues(
      of(emptyAiQueries),
      of({
        total: 2,
        items: [
          {
            id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            query_text: 'What is Northwind?',
            category: 'BRAND',
            created_at: '2026-03-02T12:05:00Z',
            has_response: true,
          },
          {
            id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
            query_text: 'Who competes with Northwind?',
            category: 'COMPETITOR',
            created_at: '2026-03-02T12:05:00Z',
            has_response: false,
          },
        ],
      }),
    );
    aiQueries.get.and.returnValue(
      of({
        id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        audit_id: audit.id,
        query_text: 'What is Northwind?',
        category: 'BRAND',
        created_at: '2026-03-02T12:05:00Z',
        response: {
          id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
          provider: 'mock',
          model: 'mock-deterministic-v1',
          response_text: 'Northwind sells outdoor goods.',
          brand_mentioned: true,
          brand_position: 1,
          citation_found: false,
          semantic_alignment: null,
          latency_ms: 5,
          created_at: '2026-03-02T12:05:01Z',
        },
      }),
    );

    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const button = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('Run AI Analysis'),
    ) as HTMLButtonElement;
    button.click();
    harness.detectChanges();
    expect(component.runningAiQueries()).toBeTrue();
    expect(harness.fixture.nativeElement.textContent).toContain('Running AI query analysis');

    run$.next({
      audit_id: audit.id,
      queries_generated: 18,
      responses_succeeded: 16,
      responses_failed: 2,
      status: 'COMPLETED',
    });
    run$.complete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    let text = harness.fixture.nativeElement.textContent as string;
    expect(aiQueries.run).toHaveBeenCalledWith(audit.id);
    expect(text).toContain('18 queries, 16 responses (2 failed)');
    expect(text).toContain('What is Northwind?');
    expect(text).toContain('BRAND');
    expect(text).toContain('No response');

    const expand = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('What is Northwind?'),
    ) as HTMLButtonElement;
    expand.click();
    await harness.fixture.whenStable();
    harness.detectChanges();
    text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Northwind sells outdoor goods.');
    expect(text).toContain('Brand mentioned');
    expect(text).toContain('Yes');
    expect(text).toContain('Semantic alignment');
    expect(text).toMatch(/Semantic alignment\s*—/);
  });

  it('shows AI query error state', async () => {
    aiQueries.run.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 422,
            error: { detail: 'Brand name and industry are required before running AI query analysis.' },
          }),
      ),
    );
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    component.runAiAnalysis();
    await harness.fixture.whenStable();
    harness.detectChanges();
    expect(harness.fixture.nativeElement.textContent).toContain(
      'Brand name and industry are required before running AI query analysis.',
    );
  });


  it('calculates and displays AI Visibility metrics', async () => {
    const calc$ = new Subject<AIVisibilityResponse>();
    visibilityApi.calculateVisibility.and.returnValue(calc$.asObservable());
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const button = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('Calculate AI Visibility'),
    ) as HTMLButtonElement;
    button.click();
    harness.detectChanges();
    expect(component.calculatingVisibility()).toBeTrue();
    expect(harness.fixture.nativeElement.textContent).toContain('Calculating AI Visibility');

    calc$.next({
      audit_id: audit.id,
      status: 'PROVISIONAL',
      overall_score: 72.4,
      metrics: {
        mention_rate: 0.78,
        citation_rate: 0.62,
        average_position: 1.9,
        position_score: 77.5,
        semantic_alignment: 0.71,
        semantic_score: 71.0,
      },
      components: { mention: 78, citation: 62, position: 77.5, semantic: 71 },
      total_queries: 18,
      successful_responses: 16,
      failed_responses: 2,
      response_coverage: 0.8889,
      note: 'AI Visibility is provisional because some AI queries have no response.',
    });
    calc$.complete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(visibilityApi.calculateVisibility).toHaveBeenCalledWith(audit.id);
    expect(text).toContain('72.4 / 100');
    expect(text).toContain('Mention Rate');
    expect(text).toContain('78.0%');
    expect(text).toContain('Citation Rate');
    expect(text).toContain('Position Score');
    expect(text).toContain('77.5');
    expect(text).toContain('Semantic Match');
    expect(text).toContain('71.0');
    expect(text).toContain('Successful responses');
    expect(text).toContain('16');
    expect(text).toContain('Provisional');
  });

  it('shows AI Visibility error state', async () => {
    visibilityApi.calculateVisibility.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 422,
            error: { detail: 'No analyzable AI responses for visibility.' },
          }),
      ),
    );
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    component.calculateVisibility();
    await harness.fixture.whenStable();
    harness.detectChanges();
    expect(harness.fixture.nativeElement.textContent).toContain(
      'No analyzable AI responses for visibility.',
    );
  });


  it('calculates and displays Entity Strength', async () => {
    const calc$ = new Subject<EntityStrengthResponse>();
    entityApi.calculateEntity.and.returnValue(calc$.asObservable());
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const button = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('Calculate Entity'),
    ) as HTMLButtonElement;
    button.click();
    harness.detectChanges();
    expect(component.calculatingEntity()).toBeTrue();
    expect(harness.fixture.nativeElement.textContent).toContain('Calculating Entity Strength');

    calc$.next({
      audit_id: audit.id,
      status: 'PROVISIONAL',
      overall_score: 74.5,
      metrics: {
        title_presence_rate: 1,
        meta_presence_rate: 0.5,
        title_consistency: 1,
        canonical_consistency: 1,
        schema_consistency: 1,
        entity_schema_coverage: 1,
        schema_quality: 1,
        ai_mention_rate: null,
        ai_position_score: null,
      },
      components: {
        presence: 75,
        consistency: 100,
        structured_identity: 100,
        ai_recognition: null,
      },
      component_details: [
        {
          name: 'presence',
          score: 75,
          status: 'AVAILABLE',
          weight: 0.3,
          effective_weight: 0.375,
          sample_size: 2,
        },
        {
          name: 'consistency',
          score: 100,
          status: 'AVAILABLE',
          weight: 0.25,
          effective_weight: 0.3125,
          sample_size: 2,
        },
        {
          name: 'structured_identity',
          score: 100,
          status: 'AVAILABLE',
          weight: 0.25,
          effective_weight: 0.3125,
          sample_size: 2,
        },
        {
          name: 'ai_recognition',
          score: null,
          status: 'UNAVAILABLE',
          weight: 0.2,
          effective_weight: null,
          sample_size: 0,
        },
      ],
      evidence: {
        analyzable_pages: 2,
        pages_with_brand_in_title: 2,
        pages_with_brand_in_meta: 1,
        pages_with_canonical: 2,
        pages_with_same_origin_canonical: 2,
        pages_with_schema: 2,
        pages_with_entity_schema: 2,
        successful_ai_responses: 0,
        responses_mentioning_brand: 0,
        average_mention_position: null,
        brand_name: 'Northwind',
        normalized_brand_name: 'northwind',
        origin: 'https://northwind.example',
      },
      notes: [
        'This score evaluates signals found on the audited website and analyzed AI responses. It does not verify Google Knowledge Graph, Wikidata, Wikipedia, or third-party entity databases.',
      ],
    });
    calc$.complete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(entityApi.calculateEntity).toHaveBeenCalledWith(audit.id);
    expect(text).toContain('74.5 / 100');
    expect(text).toContain('Entity Presence');
    expect(text).toContain('Structured Identity');
    expect(text).toContain('Pages analyzed');
    expect(text).toContain('Brand in title');
    expect(text).toContain('does not verify Google Knowledge Graph');
    expect(text).toContain('Provisional');
  });

  it('calculates and displays recommendations', async () => {
    const calc$ = new Subject<RecommendationRunResponse>();
    recommendationsApi.calculateRecommendations.and.returnValue(calc$.asObservable());
    recommendationsApi.getRecommendations.and.returnValues(
      of(emptyRecommendations),
      of({
        total: 1,
        items: [
          {
            id: '44444444-4444-4444-8444-444444444444',
            title: 'Add missing meta descriptions',
            description: '2 of 5 analyzed pages have no meta description. Add unique descriptions.',
            category: 'SEO',
            priority: 'HIGH',
            impact_score: 78,
            effort_score: 25,
          },
        ],
      }),
    );

    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/audits/${audit.id}`, AuditDetailComponent);
    harness.detectChanges();

    const buttons = Array.from(
      harness.fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    );
    const calcBtn = buttons.find((item) =>
      item.textContent?.includes('Calculate Recommendations'),
    );
    expect(calcBtn).toBeTruthy();
    calcBtn!.click();
    harness.detectChanges();

    expect(component.calculatingRecommendations()).toBeTrue();
    expect(harness.fixture.nativeElement.textContent).toContain('Calculating recommendations');

    calc$.next({
      audit_id: audit.id,
      recommendations_generated: 1,
      high: 1,
      medium: 0,
      low: 0,
      status: 'COMPLETED',
    });
    calc$.complete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(recommendationsApi.calculateRecommendations).toHaveBeenCalledWith(audit.id);
    expect(text).toContain('Add missing meta descriptions');
    expect(text).toContain('High priority');
    expect(text).toContain('Estimated impact');
    expect(text).toContain('Estimated effort');
    expect(text).toContain('2 of 5 analyzed pages');
    expect(text).not.toContain('best recommendation');
    expect(text).not.toContain('guaranteed impact');
  });

});
