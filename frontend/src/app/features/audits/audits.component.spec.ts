import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { BrandService } from '../brands/brand.service';
import { AuditSummary } from './audit.models';
import { AuditService } from './audit.service';
import { AuditsComponent } from './audits.component';

const brandId = '11111111-1111-4111-8111-111111111111';
const auditId = '22222222-2222-4222-8222-222222222222';

const scored: AuditSummary = {
  id: auditId,
  brand_id: brandId,
  status: 'COMPLETED',
  pages_crawled: 4,
  overall_score: 72,
  website_score: 80,
  seo_score: 64,
  ai_visibility_score: null,
  entity_score: null,
  semantic_score: null,
  started_at: '2026-09-01T12:00:00Z',
  completed_at: '2026-09-01T12:30:00Z',
  created_at: '2026-09-01T12:00:00Z',
};

const zeroScore: AuditSummary = {
  ...scored,
  id: '33333333-3333-4333-8333-333333333333',
  overall_score: 0,
  website_score: 0,
  seo_score: 0,
  ai_visibility_score: 0,
  entity_score: 0,
  created_at: '2026-08-01T12:00:00Z',
};

describe('AuditsComponent', () => {
  let fixture: ComponentFixture<AuditsComponent>;
  let brands: jasmine.SpyObj<BrandService>;
  let audits: jasmine.SpyObj<AuditService>;

  beforeEach(async () => {
    brands = jasmine.createSpyObj('BrandService', ['listBrands']);
    audits = jasmine.createSpyObj('AuditService', ['listAudits']);
    await TestBed.configureTestingModule({
      imports: [AuditsComponent],
      providers: [
        provideRouter([
          { path: 'audits', component: AuditsComponent },
          { path: 'audits/:id', component: AuditsComponent },
          { path: 'brands', component: AuditsComponent },
          { path: 'login', component: AuditsComponent },
        ]),
        { provide: BrandService, useValue: brands },
        { provide: AuditService, useValue: audits },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(AuditsComponent);
    fixture.detectChanges();
  }

  it('renders owned audits and does not show missing scores as zero', () => {
    brands.listBrands.and.returnValue(
      of({
        items: [
          {
            id: brandId,
            name: 'Northwind',
            website_url: null,
            industry: null,
            country: null,
            target_market: null,
            description: null,
            created_at: '2026-09-01T12:00:00Z',
            updated_at: '2026-09-01T12:00:00Z',
          },
        ],
        total: 1,
      }),
    );
    audits.listAudits.and.returnValue(of({ items: [scored, zeroScore] }));
    create();

    const rows = fixture.nativeElement.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
    const firstCells = (rows[0] as HTMLElement).querySelectorAll('td');
    expect(firstCells[6].textContent).toContain('—');
    expect(firstCells[7].textContent).toContain('—');
    expect(firstCells[6].textContent).not.toContain('0 / 100');
    expect(firstCells[7].textContent).not.toContain('0 / 100');
    const secondCells = (rows[1] as HTMLElement).querySelectorAll('td');
    expect(secondCells[6].textContent).toContain('0 / 100');
    const link = fixture.nativeElement.querySelector(`a[href="/audits/${auditId}"]`) as HTMLAnchorElement;
    expect(link).not.toBeNull();
    expect(audits.listAudits).toHaveBeenCalledWith(brandId, 50);
    expect(fixture.nativeElement.textContent).toContain('Provisional');
    expect(fixture.nativeElement.textContent).toContain('Not calculated');
  });

  it('shows an empty state with a link to brands', () => {
    brands.listBrands.and.returnValue(of({ items: [], total: 0 }));
    create();

    expect(fixture.nativeElement.textContent).toContain('No audits yet');
    const link = fixture.nativeElement.querySelector('a[href="/brands"]') as HTMLAnchorElement;
    expect(link.textContent).toContain('Open brands');
  });

  it('shows an error state when the audit list fails', () => {
    brands.listBrands.and.returnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    create();

    expect(fixture.nativeElement.textContent).toContain('Unable to load audits');
    expect(fixture.nativeElement.textContent).toContain('Something went wrong. Please try again.');
  });

  it('sends unauthenticated visitors to login', async () => {
    brands.listBrands.and.returnValue(throwError(() => new HttpErrorResponse({ status: 401 })));
    create();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/login');
  });
});
