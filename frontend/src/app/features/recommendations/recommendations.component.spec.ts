import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { RecommendationListResponse } from '../audits/recommendation.models';
import { RecommendationService } from '../audits/recommendation.service';
import { IntelligenceAuditList } from '../intelligence-chat/intelligence.models';
import { IntelligenceService } from '../intelligence-chat/intelligence.service';
import { RecommendationsComponent } from './recommendations.component';

const auditId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

const catalog: IntelligenceAuditList = {
  audits: [
    {
      id: auditId,
      brand_id: '11111111-1111-4111-8111-111111111111',
      brand_name: 'Northwind',
      status: 'COMPLETED',
      created_at: '2026-09-23T12:00:00Z',
      completed_at: '2026-09-23T12:30:00Z',
    },
  ],
  selected_audit_id: auditId,
};

const list: RecommendationListResponse = {
  total: 2,
  items: [
    {
      id: 'low-1',
      title: 'Review thin pages',
      description: 'A few pages have very little copy.',
      category: 'CONTENT',
      priority: 'LOW',
      impact_score: 20,
      effort_score: 15,
    },
    {
      id: 'high-1',
      title: 'Add meta descriptions',
      description: 'About page is missing a meta description.',
      category: 'SEO',
      priority: 'HIGH',
      impact_score: 90,
      effort_score: null,
    },
  ],
};

describe('RecommendationsComponent', () => {
  let fixture: ComponentFixture<RecommendationsComponent>;
  let intelligence: jasmine.SpyObj<IntelligenceService>;
  let recommendationsApi: jasmine.SpyObj<RecommendationService>;

  beforeEach(async () => {
    intelligence = jasmine.createSpyObj('IntelligenceService', ['getAudits']);
    recommendationsApi = jasmine.createSpyObj('RecommendationService', ['getRecommendations']);
    await TestBed.configureTestingModule({
      imports: [RecommendationsComponent],
      providers: [
        provideRouter([{ path: 'recommendations', component: RecommendationsComponent }]),
        { provide: IntelligenceService, useValue: intelligence },
        { provide: RecommendationService, useValue: recommendationsApi },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(RecommendationsComponent);
    fixture.detectChanges();
  }

  it('renders recommendations in API order with priority, impact, and effort', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    recommendationsApi.getRecommendations.and.returnValue(of(list));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text.indexOf('Review thin pages')).toBeLessThan(text.indexOf('Add meta descriptions'));
    expect(text).toContain('Low priority');
    expect(text).toContain('High priority');
    expect(text).toContain('Content');
    expect(text).toContain('SEO');
    expect(text).toContain('Impact');
    expect(text).toContain('90');
    expect(text).toContain('Effort');
    expect(text).toContain('Northwind');
    const auditLink = fixture.nativeElement.querySelector(`a[href="/audits/${auditId}"]`);
    expect(auditLink).not.toBeNull();
  });

  it('shows an empty state when the audit has no recommendations', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    recommendationsApi.getRecommendations.and.returnValue(of({ items: [], total: 0 }));
    create();

    expect(fixture.nativeElement.textContent).toContain('No recommendations yet');
    expect(fixture.nativeElement.textContent).toContain('Open audit');
  });

  it('shows an empty state when the user has no audits', () => {
    intelligence.getAudits.and.returnValue(of({ audits: [], selected_audit_id: null }));
    create();

    expect(fixture.nativeElement.textContent).toContain('No audits to review yet');
    expect(recommendationsApi.getRecommendations).not.toHaveBeenCalled();
  });

  it('shows an error state when recommendations fail to load', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    recommendationsApi.getRecommendations.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 404 })),
    );
    create();

    expect(fixture.nativeElement.textContent).toContain('Unable to load recommendations');
    expect(fixture.nativeElement.textContent).toContain('That audit could not be found.');
  });
});
