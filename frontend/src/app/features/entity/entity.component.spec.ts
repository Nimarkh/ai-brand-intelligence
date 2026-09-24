import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { EntityStrengthResponse } from '../audits/entity.models';
import { EntityService } from '../audits/entity.service';
import { IntelligenceAuditList } from '../intelligence-chat/intelligence.models';
import { IntelligenceService } from '../intelligence-chat/intelligence.service';
import { EntityComponent } from './entity.component';

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

const entity: EntityStrengthResponse = {
  audit_id: auditId,
  status: 'UNAVAILABLE',
  overall_score: null,
  metrics: {
    title_presence_rate: null,
    meta_presence_rate: null,
    title_consistency: null,
    canonical_consistency: null,
    schema_consistency: null,
    entity_schema_coverage: null,
    schema_quality: null,
    ai_mention_rate: null,
    ai_position_score: null,
  },
  components: {
    presence: null,
    consistency: null,
    structured_identity: null,
    ai_recognition: null,
  },
  component_details: [
    {
      name: 'presence',
      score: null,
      status: 'UNAVAILABLE',
      weight: 0.3,
      effective_weight: null,
      sample_size: 0,
    },
  ],
  evidence: {
    analyzable_pages: 0,
    pages_with_brand_in_title: 0,
    pages_with_brand_in_meta: 0,
    pages_with_canonical: 0,
    pages_with_same_origin_canonical: 0,
    pages_with_schema: 0,
    pages_with_entity_schema: 0,
    successful_ai_responses: 0,
    responses_mentioning_brand: 0,
    average_mention_position: null,
    brand_name: 'Northwind',
    normalized_brand_name: 'northwind',
    origin: null,
  },
  notes: [],
};

describe('EntityComponent', () => {
  let fixture: ComponentFixture<EntityComponent>;
  let intelligence: jasmine.SpyObj<IntelligenceService>;
  let entityApi: jasmine.SpyObj<EntityService>;

  beforeEach(async () => {
    intelligence = jasmine.createSpyObj('IntelligenceService', ['getAudits']);
    entityApi = jasmine.createSpyObj('EntityService', ['getEntity']);
    await TestBed.configureTestingModule({
      imports: [EntityComponent],
      providers: [
        provideRouter([{ path: 'entity', component: EntityComponent }]),
        { provide: IntelligenceService, useValue: intelligence },
        { provide: EntityService, useValue: entityApi },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(EntityComponent);
    fixture.detectChanges();
  }

  it('renders stored component metrics', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    entityApi.getEntity.and.returnValue(
      of({
        ...entity,
        status: 'PROVISIONAL',
        overall_score: 61.2,
        components: {
          presence: 80,
          consistency: null,
          structured_identity: 40,
          ai_recognition: null,
        },
        evidence: {
          ...entity.evidence,
          analyzable_pages: 5,
          pages_with_brand_in_title: 3,
          pages_with_schema: 2,
          pages_with_entity_schema: 1,
        },
        metrics: { ...entity.metrics, canonical_consistency: 0.8 },
        notes: ['It does not verify Google Knowledge Graph, Wikidata, Wikipedia, or third-party entity databases.'],
      }),
    );
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Entity Presence');
    expect(text).toContain('80.0');
    expect(text).toContain('Entity Consistency');
    expect(text).toContain('Structured Identity');
    expect(text).toContain('AI Recognition');
    expect(text).toContain('Provisional');
    expect(text).toContain('Not available');
    expect(text).toContain('Brand occurrences in titles');
    expect(text).toContain('not an external knowledge graph');
    expect(text).toContain('Wikidata');
  });

  it('shows an empty state when crawl and AI evidence are missing', () => {
    intelligence.getAudits.and.returnValue(of(catalog));
    entityApi.getEntity.and.returnValue(of(entity));
    create();

    expect(fixture.nativeElement.textContent).toContain('No crawl or AI response data');
    expect(fixture.nativeElement.textContent).not.toContain('0 / 100');
  });

  it('shows an empty state when the user has no audits', () => {
    intelligence.getAudits.and.returnValue(of({ audits: [], selected_audit_id: null }));
    create();

    expect(fixture.nativeElement.textContent).toContain('No audits to review yet');
    expect(entityApi.getEntity).not.toHaveBeenCalled();
  });

  it('shows an error state when entity data fails to load', () => {
    intelligence.getAudits.and.returnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    create();

    expect(fixture.nativeElement.textContent).toContain('Unable to load Entity Intelligence');
  });
});
