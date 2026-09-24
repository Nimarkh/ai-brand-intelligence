import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, throwError } from 'rxjs';

import { AuditService } from '../audits/audit.service';
import { ToastService } from '../../shared/components/toast/toast.service';
import { Brand } from './brand.models';
import { BrandDetailComponent } from './brand-detail.component';
import { BrandFormComponent } from './brand-form.component';
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

describe('BrandFormComponent', () => {
  let brands: jasmine.SpyObj<BrandService>;
  let toast: jasmine.SpyObj<ToastService>;

  beforeEach(() => {
    brands = jasmine.createSpyObj('BrandService', ['listBrands', 'getBrand', 'createBrand', 'updateBrand', 'deleteBrand']);
    toast = jasmine.createSpyObj('ToastService', ['show']);
    brands.listBrands.and.returnValue(of({ items: [], total: 0 }));
    brands.getBrand.and.returnValue(of(brand));
    const audits = jasmine.createSpyObj('AuditService', ['listAudits', 'createAudit', 'crawl']);
    audits.listAudits.and.returnValue(of({ items: [] }));

    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'brands/new', component: BrandFormComponent, data: { mode: 'create', title: 'Add brand' } },
          { path: 'brands/:id/edit', component: BrandFormComponent, data: { mode: 'edit', title: 'Edit brand' } },
          { path: 'brands/:id', component: BrandDetailComponent },
          { path: 'brands', component: BrandsComponent },
        ]),
        { provide: BrandService, useValue: brands },
        { provide: AuditService, useValue: audits },
        { provide: ToastService, useValue: { ...toast, toasts: signal([]) } },
      ],
    });
  });

  function validValue(overrides: Partial<typeof brand> = {}) {
    return {
      name: overrides.name ?? 'Northwind',
      website_url: overrides.website_url ?? 'https://northwind.example',
      industry: 'Retail',
      country: 'United States',
      target_market: 'North America',
      description: overrides.description ?? '',
    };
  }

  it('keeps create disabled until the form is valid and shows validation', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/brands/new', BrandFormComponent);
    const button = harness.fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement;

    expect(harness.fixture.nativeElement.textContent).toContain('Create brand');
    expect(button.disabled).toBeTrue();
    expect(brands.getBrand).not.toHaveBeenCalled();

    component.form.setValue(validValue({ name: '   ', website_url: 'javascript:alert(1)' }));
    component.onSubmit();
    harness.detectChanges();

    expect(button.disabled).toBeTrue();
    expect(brands.createBrand).not.toHaveBeenCalled();
    expect(harness.fixture.nativeElement.textContent).toContain('Enter a brand name.');
    expect(harness.fixture.nativeElement.textContent).toContain('Enter a valid http or https URL.');
  });

  it('creates a brand and opens its overview', async () => {
    brands.createBrand.and.returnValue(of(brand));
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/brands/new', BrandFormComponent);

    component.form.setValue(validValue({ description: '  Outdoor goods  ' }));
    harness.detectChanges();
    expect((harness.fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeFalse();

    component.onSubmit();
    await harness.fixture.whenStable();
    harness.detectChanges();

    expect(brands.createBrand).toHaveBeenCalledWith({
      name: 'Northwind',
      website_url: 'https://northwind.example',
      industry: 'Retail',
      country: 'United States',
      target_market: 'North America',
      description: 'Outdoor goods',
    });
    expect(toast.show).toHaveBeenCalledWith('success', 'Brand created.');
    expect(TestBed.inject(Router).url).toBe(`/brands/${brand.id}`);
    expect(harness.fixture.nativeElement.textContent).toContain('Brand overview');
    expect(harness.fixture.nativeElement.textContent).not.toContain('Sample data');
  });

  it('shows an API validation error and stays on the form', async () => {
    brands.createBrand.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 422,
            statusText: 'Unprocessable Entity',
            error: { detail: [{ msg: 'website_url must use http or https' }] },
          }),
      ),
    );
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/brands/new', BrandFormComponent);
    component.form.setValue(validValue());
    component.onSubmit();
    harness.detectChanges();

    expect(harness.fixture.nativeElement.textContent).toContain('website_url must use http or https');
    expect(component.submitting()).toBeFalse();
    expect(TestBed.inject(Router).url).toBe('/brands/new');
  });

  it('prefills the edit form and saves changes', async () => {
    const updated = { ...brand, name: 'Northwind Goods' };
    brands.updateBrand.and.returnValue(of(updated));
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl(`/brands/${brand.id}/edit`, BrandFormComponent);

    expect(component.form.controls.name.value).toBe('Northwind');
    expect(component.form.controls.website_url.value).toBe('https://northwind.example');
    expect(harness.fixture.nativeElement.textContent).toContain('Save changes');

    component.form.controls.name.setValue('Northwind Goods');
    component.onSubmit();
    await harness.fixture.whenStable();
    harness.detectChanges();

    const payload = brands.updateBrand.calls.mostRecent().args[1] as { owner_id?: string; name: string };
    expect(brands.updateBrand).toHaveBeenCalledWith(brand.id, jasmine.any(Object));
    expect(payload.name).toBe('Northwind Goods');
    expect(payload.owner_id).toBeUndefined();
    expect(toast.show).toHaveBeenCalledWith('success', 'Brand updated.');
    expect(TestBed.inject(Router).url).toBe(`/brands/${brand.id}`);
  });
});
