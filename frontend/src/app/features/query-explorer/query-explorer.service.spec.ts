import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { credentialsInterceptor } from '../../core/interceptors/credentials.interceptor';
import { QueryExplorerView } from './query-explorer.models';
import { QueryExplorerService } from './query-explorer.service';

describe('QueryExplorerService', () => {
  let service: QueryExplorerService;
  let httpTesting: HttpTestingController;

  const view: QueryExplorerView = {
    audit: null,
    audits: [],
    summary: null,
    items: [],
    pagination: { page: 1, page_size: 20, total: 0, pages: 0 },
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([credentialsInterceptor])), provideHttpClientTesting()],
    });
    service = TestBed.inject(QueryExplorerService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('loads explorer data with credentials and default pagination', () => {
    service.getExplorerData().subscribe((result) => {
      expect(result).toEqual(view);
    });

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/query-explorer?page=1&page_size=20`,
    );
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush(view);
  });

  it('sends audit, filter, and pagination parameters', () => {
    service
      .getExplorerData({
        auditId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        category: 'BRAND',
        search: '  northwind  ',
        hasResponse: false,
        brandMentioned: true,
        citationFound: false,
        page: 2,
        pageSize: 50,
      })
      .subscribe();

    const request = httpTesting.expectOne((candidate) =>
      candidate.url === `${environment.apiBaseUrl}/query-explorer`,
    );
    expect(request.request.params.get('audit_id')).toBe('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
    expect(request.request.params.get('category')).toBe('BRAND');
    expect(request.request.params.get('search')).toBe('northwind');
    expect(request.request.params.get('has_response')).toBe('false');
    expect(request.request.params.get('brand_mentioned')).toBe('true');
    expect(request.request.params.get('citation_found')).toBe('false');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('50');
    request.flush(view);
  });
});
