import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { EntityStrengthResponse } from './entity.models';
import { EntityService } from './entity.service';

describe('EntityService', () => {
  let service: EntityService;
  let http: HttpTestingController;
  const auditId = '22222222-2222-4222-8222-222222222222';

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });
    service = TestBed.inject(EntityService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('calculates entity strength', () => {
    let body: EntityStrengthResponse | undefined;
    service.calculateEntity(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/calculate-entity`);
    expect(req.request.method).toBe('POST');
    req.flush({
      audit_id: auditId,
      status: 'AVAILABLE',
      overall_score: 81.2,
      metrics: {
        title_presence_rate: 1,
        meta_presence_rate: 1,
        title_consistency: 1,
        canonical_consistency: 1,
        schema_consistency: 1,
        entity_schema_coverage: 1,
        schema_quality: 1,
        ai_mention_rate: 1,
        ai_position_score: 100,
      },
      components: {
        presence: 100,
        consistency: 100,
        structured_identity: 100,
        ai_recognition: 100,
      },
      component_details: [],
      evidence: {
        analyzable_pages: 2,
        pages_with_brand_in_title: 2,
        pages_with_brand_in_meta: 2,
        pages_with_canonical: 2,
        pages_with_same_origin_canonical: 2,
        pages_with_schema: 2,
        pages_with_entity_schema: 2,
        successful_ai_responses: 4,
        responses_mentioning_brand: 4,
        average_mention_position: 1,
        brand_name: 'Acme',
        normalized_brand_name: 'acme',
        origin: 'https://acme.example',
      },
      notes: ['Limitation note'],
    });
    expect(body?.overall_score).toBe(81.2);
  });

  it('gets entity strength', () => {
    let body: EntityStrengthResponse | undefined;
    service.getEntity(auditId).subscribe((response) => (body = response));
    const req = http.expectOne(`${environment.apiBaseUrl}/audits/${auditId}/entity`);
    expect(req.request.method).toBe('GET');
    req.flush({
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
      component_details: [],
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
        brand_name: 'Acme',
        normalized_brand_name: 'acme',
        origin: null,
      },
      notes: [],
    });
    expect(body?.status).toBe('UNAVAILABLE');
  });
});
