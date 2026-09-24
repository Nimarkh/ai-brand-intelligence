import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { environment } from '../../../environments/environment';
import {
  RecommendationListResponse,
  RecommendationRunResponse,
} from './recommendation.models';
import { RecommendationService } from './recommendation.service';

describe('RecommendationService', () => {
  let service: RecommendationService;
  let http: HttpTestingController;
  const auditId = '22222222-2222-4222-8222-222222222222';

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(RecommendationService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('calculates recommendations', () => {
    let body: RecommendationRunResponse | undefined;
    service.calculateRecommendations(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(
      `${environment.apiBaseUrl}/audits/${auditId}/calculate-recommendations`,
    );
    expect(req.request.method).toBe('POST');
    req.flush({
      audit_id: auditId,
      recommendations_generated: 2,
      high: 1,
      medium: 1,
      low: 0,
      status: 'COMPLETED',
    });
    expect(body?.recommendations_generated).toBe(2);
    expect(body?.status).toBe('COMPLETED');
  });

  it('gets recommendations', () => {
    let body: RecommendationListResponse | undefined;
    service.getRecommendations(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/recommendations`);
    expect(req.request.method).toBe('GET');
    const payload: RecommendationListResponse = {
      total: 1,
      items: [
        {
          id: '33333333-3333-4333-8333-333333333333',
          title: 'Add missing meta descriptions',
          description: '2 of 5 analyzed pages have no meta description.',
          category: 'SEO',
          priority: 'HIGH',
          impact_score: 80,
          effort_score: 25,
        },
      ],
    };
    req.flush(payload);
    expect(body?.total).toBe(1);
    expect(body?.items[0].title).toBe('Add missing meta descriptions');
  });
});
