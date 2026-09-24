import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { environment } from '../../../environments/environment';
import { credentialsInterceptor } from '../../core/interceptors/credentials.interceptor';
import { IntelligenceService } from './intelligence.service';

describe('IntelligenceService', () => {
  let service: IntelligenceService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([credentialsInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(IntelligenceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('loads owned audits with an optional audit id', () => {
    service.getAudits('audit-1').subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/intelligence/audits?audit_id=audit-1`);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ audits: [], selected_audit_id: null });
  });

  it('asks with a strict body and does not call a provider URL', () => {
    service
      .ask({
        audit_id: 'audit-1',
        question: 'Why is my score low?',
        history: [{ role: 'user', content: 'Earlier question' }],
      })
      .subscribe();

    const request = http.expectOne(`${environment.apiBaseUrl}/intelligence/ask`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      audit_id: 'audit-1',
      question: 'Why is my score low?',
      history: [{ role: 'user', content: 'Earlier question' }],
    });
    expect(JSON.stringify(request.request.body)).not.toContain('sk-');
    request.flush({
      audit_id: 'audit-1',
      answer: 'Based on the selected audit.',
      context: {
        brand_name: 'Acme',
        audit_date: '2026-09-23T12:00:00Z',
        overall_score: 72,
        overall_status: 'PROVISIONAL',
      },
      sources: [],
      empty: false,
      message: null,
    });
  });
});
