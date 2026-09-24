import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { ToastService } from '../../shared/components/toast/toast.service';
import { Brand } from './brand.models';
import { BrandService } from './brand.service';
import { BrandsComponent } from './brands.component';

@Component({ standalone: true, template: 'Sign in' })
class LoginStubComponent {}

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

describe('BrandsComponent', () => {
  let fixture: ComponentFixture<BrandsComponent>;
  let brands: jasmine.SpyObj<BrandService>;

  beforeEach(async () => {
    brands = jasmine.createSpyObj('BrandService', ['listBrands']);
    spyOn(localStorage, 'setItem');

    await TestBed.configureTestingModule({
      imports: [BrandsComponent],
      providers: [
        provideRouter([
          { path: 'brands', component: BrandsComponent },
          { path: 'brands/new', component: BrandsComponent },
          { path: 'brands/:id', component: BrandsComponent },
          { path: 'login', component: LoginStubComponent },
        ]),
        { provide: BrandService, useValue: brands },
        { provide: ToastService, useValue: { show: jasmine.createSpy('show'), toasts: signal([]) } },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(BrandsComponent);
    fixture.detectChanges();
  }

  it('shows a loading state and then the empty state', () => {
    const pending = new Subject<{ items: Brand[]; total: number }>();
    brands.listBrands.and.returnValue(pending.asObservable());
    create();

    expect(fixture.nativeElement.textContent).toContain('Loading brands');
    expect(fixture.nativeElement.textContent).toContain('Manage the brands you want to monitor and analyze.');

    pending.next({ items: [], total: 0 });
    pending.complete();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('No brands yet.');
    expect(fixture.nativeElement.textContent).toContain('analyzing its website and AI Visibility');
    const add = fixture.nativeElement.querySelector('a[href="/brands/new"]') as HTMLAnchorElement;
    expect(add.textContent).toContain('Add brand');
    expect(localStorage.setItem).not.toHaveBeenCalled();
  });

  it('renders owned brands as links', () => {
    brands.listBrands.and.returnValue(of({ items: [brand], total: 1 }));
    create();

    const card = fixture.nativeElement.querySelector('a.brand-card') as HTMLAnchorElement;
    expect(card.getAttribute('href')).toBe(`/brands/${brand.id}`);
    expect(card.textContent).toContain('Northwind');
    expect(card.textContent).toContain('https://northwind.example');
    expect(card.textContent).toContain('Retail');
    expect(card.textContent).toContain('North America');
    expect(card.textContent).toContain('Mar 1, 2026');
    expect(card.textContent).toContain('Open');
  });

  it('shows an error and retries the list', () => {
    brands.listBrands.and.returnValues(
      throwError(() => new HttpErrorResponse({ status: 500, statusText: 'Server Error' })),
      of({ items: [], total: 0 }),
    );
    create();

    expect(fixture.nativeElement.textContent).toContain("Couldn't load brands");
    expect(fixture.nativeElement.textContent).toContain('Something went wrong. Please try again.');

    const retry = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Try again'),
    ) as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    expect(brands.listBrands).toHaveBeenCalledTimes(2);
    expect(fixture.nativeElement.textContent).toContain('No brands yet.');
  });

  it('sends an expired session back to login', async () => {
    brands.listBrands.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 401, statusText: 'Unauthorized' })),
    );
    create();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/login');
  });
});
