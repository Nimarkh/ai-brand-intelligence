import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, Subject, throwError } from 'rxjs';

import { AuditService } from '../audits/audit.service';
import { AuditSummary } from '../audits/audit.models';
import { ToastService } from '../../shared/components/toast/toast.service';
import { Brand } from './brand.models';
import { BrandDetailComponent } from './brand-detail.component';
import { BrandService } from './brand.service';
import { BrandsComponent } from './brands.component';

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

const pendingAudit: AuditSummary = {
  id: '22222222-2222-4222-8222-222222222222',
  brand_id: brand.id,
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
  created_at: '2026-03-02T12:00:00Z',
};

describe('BrandDetailComponent', () => {
  let brands: jasmine.SpyObj<BrandService>;
  let audits: jasmine.SpyObj<AuditService>;
  let toast: jasmine.SpyObj<ToastService>;

  beforeEach(() => {
    brands = jasmine.createSpyObj('BrandService', ['listBrands', 'getBrand', 'createBrand', 'updateBrand', 'deleteBrand']);
    audits = jasmine.createSpyObj('AuditService', ['listAudits', 'createAudit', 'crawl']);
    toast = jasmine.createSpyObj('ToastService', ['show']);
    brands.listBrands.and.returnValue(of({ items: [brand], total: 1 }));
    brands.getBrand.and.returnValue(of(brand));
    audits.listAudits.and.returnValue(of({ items: [] }));

    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'brands/:id', component: BrandDetailComponent },
          { path: 'brands', component: BrandsComponent },
          { path: 'login', component: BrandsComponent },
        ]),
        { provide: BrandService, useValue: brands },
        { provide: AuditService, useValue: audits },
        { provide: ToastService, useValue: { ...toast, toasts: signal([]) } },
      ],
    });
  });

  it('loads the brand overview without fake audit data', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Northwind');
    expect(text).toContain('https://northwind.example');
    expect(text).toContain('Retail');
    expect(text).toContain('United States');
    expect(text).toContain('North America');
    expect(text).toContain('Outdoor goods');
    expect(text).toContain('Start website crawl');
    expect(text).toContain('No audits yet');
    expect(text).toContain('AI visibility analysis will appear here after an audit.');
    expect(text).toContain('Recommendations will appear here after analysis.');
    expect(text).not.toContain('Sample data');
    expect(text).not.toContain('/ 100');
    expect(text).toContain('Edit');
    expect(harness.fixture.nativeElement.querySelector('a[href*="/edit"]')).not.toBeNull();
  });

  it('shows a not-found state without implying another owner', async () => {
    brands.getBrand.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found', error: { detail: 'Brand not found.' } })),
    );
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Brand not found');
    expect(text).not.toContain('another user');
    expect(text).not.toContain('Forbidden');
    expect(harness.fixture.nativeElement.querySelector('a[href="/brands"]')).not.toBeNull();
  });

  it('requires confirmation before deleting and then returns to the list', async () => {
    brands.deleteBrand.and.returnValue(of(undefined));
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);

    const deleteButton = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.trim() === 'Delete',
    ) as HTMLButtonElement;
    deleteButton.click();
    harness.detectChanges();

    expect(brands.deleteBrand).not.toHaveBeenCalled();
    expect(harness.fixture.nativeElement.textContent).toContain(`Delete ${brand.name}?`);
    expect(harness.fixture.nativeElement.textContent).toContain('permanently removes the brand');

    component.confirmDelete();
    await harness.fixture.whenStable();
    harness.detectChanges();

    expect(brands.deleteBrand).toHaveBeenCalledWith(brand.id);
    expect(toast.show).toHaveBeenCalledWith('success', 'Northwind was deleted.');
    expect(TestBed.inject(Router).url).toBe('/brands');
    expect(harness.fixture.nativeElement.textContent).toContain('Northwind');
  });

  it('stays on the brand when deletion fails', async () => {
    brands.deleteBrand.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' })),
    );
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);
    component.openDelete();
    harness.detectChanges();
    component.confirmDelete();
    harness.detectChanges();

    expect(TestBed.inject(Router).url).toBe(`/brands/${brand.id}`);
    expect(harness.fixture.nativeElement.textContent).toContain('Something went wrong. Please try again.');
    expect(component.deleting()).toBeFalse();
  });

  it('shows the latest audit status without a score', async () => {
    audits.listAudits.and.returnValue(
      of({
        items: [{ ...pendingAudit, status: 'COMPLETED', pages_crawled: 4, overall_score: 42.5 }],
      }),
    );
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Website crawl completed');
    expect(text).toContain('Website crawl completed — 4 pages crawled.');
    expect(text).toContain('Open audit / Analyze SEO');
    expect(text).not.toContain('42.5');
    expect(text).not.toContain('/ 100');
    expect(text).not.toContain('Healthy');
    expect(text).not.toContain('Good');
  });

  it('shows a pending audit without calling it healthy', async () => {
    audits.listAudits.and.returnValue(of({ items: [pendingAudit] }));
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Audit pending');
    expect(text).not.toContain('/ 100');
  });

  it('shows a loading state and then the crawl result', async () => {
    const created = new Subject<AuditSummary>();
    const crawled = new Subject<{ audit_id: string; status: 'COMPLETED'; pages_crawled: number }>();
    audits.createAudit.and.returnValue(created.asObservable());
    audits.crawl.and.returnValue(crawled.asObservable());
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);

    const button = Array.from(harness.fixture.nativeElement.querySelectorAll('button')).find((item) =>
      (item as HTMLButtonElement).textContent?.includes('Start website crawl'),
    ) as HTMLButtonElement;
    button.click();
    harness.detectChanges();

    expect(component.crawling()).toBeTrue();
    expect(harness.fixture.nativeElement.textContent).toContain('Crawling website…');
    expect(button.disabled).toBeTrue();

    created.next(pendingAudit);
    created.complete();
    harness.detectChanges();
    expect(audits.createAudit).toHaveBeenCalledWith(brand.id);
    expect(audits.crawl).toHaveBeenCalledWith(pendingAudit.id);

    crawled.next({ audit_id: pendingAudit.id, status: 'COMPLETED', pages_crawled: 12 });
    crawled.complete();
    harness.detectChanges();

    expect(component.crawling()).toBeFalse();
    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Website crawl completed — 12 pages crawled.');
    expect(text).toContain('Website crawl completed');
    expect(text).not.toContain('/ 100');
  });

  it('shows a failure message when the crawl request fails', async () => {
    audits.createAudit.and.returnValue(of(pendingAudit));
    audits.crawl.and.returnValue(throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' })));
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/brands/${brand.id}`, BrandDetailComponent);

    component.startCrawl();
    await harness.fixture.whenStable();
    harness.detectChanges();

    const text = harness.fixture.nativeElement.textContent as string;
    expect(text).toContain('Website crawl failed. Please try again.');
    expect(text).toContain('Crawl failed');
    expect(component.crawling()).toBeFalse();
    expect(text).not.toContain('/ 100');
  });
});
