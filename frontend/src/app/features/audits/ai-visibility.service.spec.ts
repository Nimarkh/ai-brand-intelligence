import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { AIVisibilityResponse } from './ai-visibility.models';
import { AiVisibilityService } from './ai-visibility.service';

describe('AiVisibilityService', () => {
  let service: AiVisibilityService;
  let http: HttpTestingController;
  const auditId = '22222222-2222-4222-8222-222222222222';

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });
    service = TestBed.inject(AiVisibilityService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('calculates visibility', () => {
    let body: AIVisibilityResponse | undefined;
    service.calculateVisibility(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(
      `${environment.apiBaseUrl}/audits/${auditId}/calculate-ai-visibility`,
    );
    expect(req.request.method).toBe('POST');
    req.flush({
      audit_id: auditId,
      status: 'AVAILABLE',
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
      successful_responses: 18,
      failed_responses: 0,
      response_coverage: 1,
      note: null,
    });
    expect(body?.overall_score).toBe(72.4);
  });

  it('gets visibility', () => {
    let body: AIVisibilityResponse | undefined;
    service.getVisibility(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/ai-visibility`);
    expect(req.request.method).toBe('GET');
    req.flush({
      audit_id: auditId,
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
      note: 'AI Visibility is unavailable.',
    });
    expect(body?.status).toBe('UNAVAILABLE');
  });
});
