import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { credentialsInterceptor } from '../../core/interceptors/credentials.interceptor';
import { BrandService } from './brand.service';

describe('BrandService', () => {
  let service: BrandService;
  let httpTesting: HttpTestingController;

  const brand = {
    id: '11111111-1111-4111-8111-111111111111',
    name: 'Northwind',
    website_url: 'https://northwind.example',
    industry: 'Retail',
    country: 'United States',
    target_market: 'North America',
    description: null,
    created_at: '2026-03-01T12:00:00Z',
    updated_at: '2026-03-01T12:00:00Z',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([credentialsInterceptor])), provideHttpClientTesting()],
    });
    service = TestBed.inject(BrandService);
    httpTesting = TestBed.inject(HttpTestingController);
    spyOn(localStorage, 'setItem');
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('lists brands from the API without writing local storage', () => {
    service.listBrands().subscribe((result) => {
      expect(result).toEqual({ items: [brand], total: 1 });
    });

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/brands`);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ items: [brand], total: 1 });
    expect(localStorage.setItem).not.toHaveBeenCalled();
  });

  it('creates, reads, updates, and deletes a brand through the API', () => {
    const payload = {
      name: 'Northwind',
      website_url: 'https://northwind.example',
      industry: 'Retail',
      country: 'United States',
      target_market: 'North America',
      description: null,
    };

    const brandUrl = `${environment.apiBaseUrl}/brands/${brand.id}`;

    service.getBrand(brand.id).subscribe();
    const read = httpTesting.expectOne(brandUrl);
    expect(read.request.method).toBe('GET');
    expect(read.request.withCredentials).toBeTrue();
    read.flush(brand);

    service.createBrand(payload).subscribe();
    const create = httpTesting.expectOne(`${environment.apiBaseUrl}/brands`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual(payload);
    expect(create.request.body.owner_id).toBeUndefined();
    create.flush(brand);

    service.updateBrand(brand.id, payload).subscribe();
    const update = httpTesting.expectOne(brandUrl);
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body).toEqual(payload);
    update.flush(brand);

    service.deleteBrand(brand.id).subscribe();
    const remove = httpTesting.expectOne(brandUrl);
    expect(remove.request.method).toBe('DELETE');
    remove.flush(null);

    expect(localStorage.setItem).not.toHaveBeenCalled();
  });
});
