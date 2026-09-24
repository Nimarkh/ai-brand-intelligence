import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { credentialsInterceptor } from '../../core/interceptors/credentials.interceptor';
import { DashboardOverview } from './dashboard.models';
import { DashboardService } from './dashboard.service';

describe('DashboardService', () => {
  let service: DashboardService;
  let httpTesting: HttpTestingController;

  const overview: DashboardOverview = {
    workspace: { brand_count: 1, audit_count: 0, completed_audit_count: 0 },
    selected_audit: null,
    scores: {
      overall: { score: null, status: 'UNAVAILABLE', explanation: 'Not available' },
      website: {
        score: null,
        status: 'UNAVAILABLE',
        explanation: 'Not calculated yet',
      },
      seo: {
        score: null,
        status: 'UNAVAILABLE',
        explanation: 'Not calculated yet',
      },
      ai_visibility: {
        score: null,
        status: 'UNAVAILABLE',
        explanation: 'Not calculated yet',
      },
      entity: {
        score: null,
        status: 'UNAVAILABLE',
        explanation: 'Not calculated yet',
      },
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
    brands: [{ id: '11111111-1111-4111-8111-111111111111', name: 'Northwind' }],
    selection_rule: 'latest completed',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([credentialsInterceptor])), provideHttpClientTesting()],
    });
    service = TestBed.inject(DashboardService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('loads the dashboard overview from the API', () => {
    service.getOverview().subscribe((result) => {
      expect(result).toEqual(overview);
    });

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/dashboard/overview`);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush(overview);
  });

  it('passes an optional brand_id query parameter', () => {
    service.getOverview('11111111-1111-4111-8111-111111111111').subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/dashboard/overview?brand_id=11111111-1111-4111-8111-111111111111`,
    );
    expect(request.request.method).toBe('GET');
    request.flush(overview);
  });
});
