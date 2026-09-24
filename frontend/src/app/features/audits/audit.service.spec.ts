import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { credentialsInterceptor } from '../../core/interceptors/credentials.interceptor';
import { AuditSummary } from './audit.models';
import { AuditService } from './audit.service';

describe('AuditService', () => {
  let service: AuditService;
  let httpTesting: HttpTestingController;
  const brandId = '11111111-1111-4111-8111-111111111111';
  const auditId = '22222222-2222-4222-8222-222222222222';

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([credentialsInterceptor])), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuditService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('creates an audit and starts a crawl with credentials', () => {
    const audit: AuditSummary = {
      id: auditId,
      brand_id: brandId,
      status: 'PENDING',
      pages_crawled: 0,
      overall_score: null,
      website_score: null,
      seo_score: null,
      ai_visibility_score: null,
      entity_score: null,
      semantic_score: null,
      started_at: null,
      completed_at: null,
      created_at: '2026-03-01T12:00:00Z',
    };

    service.createAudit(brandId).subscribe((result) => expect(result).toEqual(audit));
    const create = httpTesting.expectOne(`${environment.apiBaseUrl}/brands/${brandId}/audits`);
    expect(create.request.method).toBe('POST');
    expect(create.request.withCredentials).toBeTrue();
    create.flush(audit);

    service.crawl(auditId).subscribe((result) => {
      expect(result).toEqual({ audit_id: auditId, status: 'COMPLETED', pages_crawled: 12 });
    });
    const crawl = httpTesting.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/crawl`);
    expect(crawl.request.method).toBe('POST');
    expect(crawl.request.withCredentials).toBeTrue();
    crawl.flush({ audit_id: auditId, status: 'COMPLETED', pages_crawled: 12 });
  });

  it('loads audits for a brand', () => {
    service.listAudits(brandId).subscribe((result) => expect(result.items).toEqual([]));
    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/brands/${brandId}/audits`);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ items: [] });
  });

  it('loads one audit', () => {
    service.getAudit(auditId).subscribe((result) => expect(result.id).toBe(auditId));
    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/audits/${auditId}`);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush({
      id: auditId,
      brand_id: brandId,
      status: 'COMPLETED',
      pages_crawled: 3,
      overall_score: null,
      website_score: null,
      seo_score: null,
      ai_visibility_score: null,
      entity_score: null,
      semantic_score: null,
      started_at: null,
      completed_at: null,
      created_at: '2026-03-01T12:00:00Z',
    });
  });

  it('analyzes SEO and lists findings with credentials', () => {
    service.analyzeSeo(auditId).subscribe((result) => {
      expect(result).toEqual({ audit_id: auditId, findings_count: 4, status: 'COMPLETED' });
    });
    const analyze = httpTesting.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/analyze-seo`);
    expect(analyze.request.method).toBe('POST');
    expect(analyze.request.withCredentials).toBeTrue();
    analyze.flush({ audit_id: auditId, findings_count: 4, status: 'COMPLETED' });

    service.listSeoFindings(auditId).subscribe((result) => {
      expect(result.total).toBe(1);
      expect(result.items[0].title).toBe('Missing page title');
    });
    const findings = httpTesting.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/seo-findings`);
    expect(findings.request.method).toBe('GET');
    expect(findings.request.withCredentials).toBeTrue();
    findings.flush({
      total: 1,
      items: [
        {
          id: '33333333-3333-4333-8333-333333333333',
          audit_id: auditId,
          page_id: null,
          category: 'TITLE',
          severity: 'HIGH',
          title: 'Missing page title',
          description: 'No title',
          recommendation: 'Add a title',
          created_at: '2026-03-01T12:00:00Z',
          page: null,
        },
      ],
    });
  });

  it('calculates and loads scores with credentials', () => {
    const payload = {
      audit_id: auditId,
      status: 'PROVISIONAL',
      website_health: { score: 90, status: 'AVAILABLE' },
      seo: { score: 88, status: 'AVAILABLE' },
      overall: { score: 89.11, status: 'PROVISIONAL' },
      components: [],
      findings_count: 0,
      affected_pages: 0,
      analyzable_pages: 2,
      ai_visibility: { score: null, status: 'UNAVAILABLE' },
      entity_strength: { score: null, status: 'UNAVAILABLE' },
      note: 'provisional',
    };

    service.calculateScore(auditId).subscribe((result) => expect(result.status).toBe('PROVISIONAL'));
    const calculate = httpTesting.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/calculate-score`);
    expect(calculate.request.method).toBe('POST');
    expect(calculate.request.withCredentials).toBeTrue();
    calculate.flush(payload);

    service.getScore(auditId).subscribe((result) => expect(result.overall.score).toBe(89.11));
    const getScore = httpTesting.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/score`);
    expect(getScore.request.method).toBe('GET');
    expect(getScore.request.withCredentials).toBeTrue();
    getScore.flush(payload);
  });
});
