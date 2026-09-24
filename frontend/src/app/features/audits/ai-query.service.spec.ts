import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { AiQueryService } from './ai-query.service';
import { AiQueryDetail, AiQueryListResponse, AiQueryRunResponse } from './ai-query.models';

describe('AiQueryService', () => {
  let service: AiQueryService;
  let http: HttpTestingController;
  const auditId = '22222222-2222-4222-8222-222222222222';
  const queryId = '33333333-3333-4333-8333-333333333333';

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });
    service = TestBed.inject(AiQueryService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('runs AI query analysis', () => {
    let body: AiQueryRunResponse | undefined;
    service.run(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/ai-queries/run`);
    expect(req.request.method).toBe('POST');
    req.flush({
      audit_id: auditId,
      queries_generated: 18,
      responses_succeeded: 16,
      responses_failed: 2,
      status: 'COMPLETED',
    });
    expect(body?.responses_failed).toBe(2);
  });

  it('lists AI queries', () => {
    let body: AiQueryListResponse | undefined;
    service.list(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/ai-queries`);
    expect(req.request.method).toBe('GET');
    req.flush({ items: [], total: 0 });
    expect(body?.total).toBe(0);
  });

  it('gets one AI query detail', () => {
    let body: AiQueryDetail | undefined;
    service.get(auditId, queryId).subscribe((response) => (body = response));
    const req = http.expectOne(
      `${environment.apiBaseUrl}/audits/${auditId}/ai-queries/${queryId}`,
    );
    expect(req.request.method).toBe('GET');
    req.flush({
      id: queryId,
      audit_id: auditId,
      query_text: 'What is Acme?',
      category: 'BRAND',
      created_at: '2026-03-02T12:00:00Z',
      response: null,
    });
    expect(body?.response).toBeNull();
  });
});
