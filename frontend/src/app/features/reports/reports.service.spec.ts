import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { environment } from '../../../environments/environment';
import { credentialsInterceptor } from '../../core/interceptors/credentials.interceptor';
import { ReportsService } from './reports.service';

describe('ReportsService', () => {
  let service: ReportsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([credentialsInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(ReportsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('lists reports and can filter by audit', () => {
    service.list('audit-1').subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/reports?audit_id=audit-1`);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ items: [], total: 0, page: 1, page_size: 20, completed_audits: [] });
  });

  it('creates a report for one audit', () => {
    service.create('audit-1').subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/reports`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ audit_id: 'audit-1' });
    request.flush({ id: 'report-1', status: 'READY' });
  });

  it('loads report metadata without requesting the file', () => {
    service.get('report-1').subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/reports/report-1`);
    expect(request.request.method).toBe('GET');
    expect(request.request.url).not.toContain('download');
    request.flush({ id: 'report-1', status: 'READY' });
  });

  it('downloads the PDF as a blob', () => {
    service.download('report-1').subscribe();
    const request = http.expectOne(`${environment.apiBaseUrl}/reports/report-1/download`);
    expect(request.request.method).toBe('GET');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['%PDF']));
  });
});
