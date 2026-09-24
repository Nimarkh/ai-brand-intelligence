import { Page, Route } from '@playwright/test';

export const USER = {
  id: '11111111-1111-4111-8111-111111111111',
  email: 'e2e@example.com',
  full_name: 'E2E User',
};

export const BRAND = {
  id: '22222222-2222-4222-8222-222222222222',
  name: 'Fixture Brand',
  website_url: 'https://fixture.test',
  industry: 'Outdoor',
  country: 'United States',
  target_market: 'North America',
  description: 'Deterministic fixture brand',
  created_at: '2026-09-23T12:00:00Z',
  updated_at: '2026-09-23T12:00:00Z',
};

export const AUDIT = {
  id: '33333333-3333-4333-8333-333333333333',
  brand_id: BRAND.id,
  status: 'COMPLETED',
  pages_crawled: 6,
  started_at: '2026-09-23T12:01:00Z',
  completed_at: '2026-09-23T12:02:00Z',
  created_at: '2026-09-23T12:00:00Z',
  overall_score: 72,
  website_score: 80,
  seo_score: 64,
  ai_visibility_score: 55,
  entity_score: 60,
  semantic_score: 50,
};

export const REPORT = {
  id: '44444444-4444-4444-8444-444444444444',
  audit_id: AUDIT.id,
  brand_name: BRAND.name,
  brand_id: BRAND.id,
  title: 'Fixture Brand — Audit Intelligence Report',
  status: 'READY',
  audit_date: AUDIT.completed_at,
  created_at: '2026-09-23T12:10:00Z',
  completed_at: '2026-09-23T12:10:01Z',
};

const COMPLETED_AUDIT_OPTION = {
  id: AUDIT.id,
  brand_id: BRAND.id,
  brand_name: BRAND.name,
  status: AUDIT.status,
  created_at: AUDIT.created_at,
  completed_at: AUDIT.completed_at,
};

const PDF_BYTES = Buffer.from('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n', 'utf8');

function dashboardOverview(options: {
  brandCreated?: boolean;
  auditCreated?: boolean;
  pipelineStep?: number;
}) {
  const brandCreated = options.brandCreated ?? true;
  const auditCreated = options.auditCreated ?? true;
  const pipelineStep = options.pipelineStep ?? 7;
  const score = (value: number | null, status: string, explanation: string) => ({
    score: value,
    status,
    explanation,
    audit_date: auditCreated ? AUDIT.completed_at : null,
  });

  return {
    workspace: {
      brand_count: brandCreated ? 1 : 0,
      audit_count: auditCreated ? 1 : 0,
      completed_audit_count: pipelineStep >= 1 && auditCreated ? 1 : 0,
    },
    selected_audit: auditCreated
      ? {
          id: AUDIT.id,
          brand_id: BRAND.id,
          brand_name: BRAND.name,
          status: AUDIT.status,
          created_at: AUDIT.created_at,
          completed_at: AUDIT.completed_at,
          website_score_available: pipelineStep >= 3,
          seo_score_available: pipelineStep >= 3,
          ai_visibility_available: pipelineStep >= 5,
          entity_available: pipelineStep >= 6,
          overall_score_available: pipelineStep >= 3,
          pages_crawled: 6,
          seo_findings: pipelineStep >= 2 ? 4 : 0,
        }
      : null,
    scores: {
      overall: score(
        pipelineStep >= 3 ? 72 : null,
        pipelineStep >= 3 ? 'PROVISIONAL' : 'UNAVAILABLE',
        pipelineStep >= 3 ? 'Provisional overall score' : 'Not calculated yet',
      ),
      website: score(
        pipelineStep >= 3 ? 80 : null,
        pipelineStep >= 3 ? 'AVAILABLE' : 'UNAVAILABLE',
        pipelineStep >= 3 ? 'Website health available' : 'Not calculated yet',
      ),
      seo: score(
        pipelineStep >= 3 ? 64 : null,
        pipelineStep >= 3 ? 'AVAILABLE' : 'UNAVAILABLE',
        pipelineStep >= 3 ? 'SEO available' : 'Not calculated yet',
      ),
      ai_visibility: score(
        pipelineStep >= 5 ? 55 : null,
        pipelineStep >= 5 ? 'AVAILABLE' : 'UNAVAILABLE',
        pipelineStep >= 5 ? 'AI visibility available' : 'Not calculated yet',
      ),
      entity: score(
        pipelineStep >= 6 ? 60 : null,
        pipelineStep >= 6 ? 'AVAILABLE' : 'UNAVAILABLE',
        pipelineStep >= 6 ? 'Entity available' : 'Not calculated yet',
      ),
    },
    snapshot: {
      pages_crawled: auditCreated ? 6 : null,
      seo_findings: pipelineStep >= 2 ? 4 : null,
      high_severity_findings: pipelineStep >= 2 ? 1 : null,
      ai_queries: pipelineStep >= 4 ? 18 : null,
      ai_successful_responses: pipelineStep >= 4 ? 18 : null,
      ai_response_coverage: pipelineStep >= 4 ? 1 : null,
      ai_mention_rate: pipelineStep >= 5 ? 0.5 : null,
      entity_pages_analyzed: pipelineStep >= 6 ? 5 : null,
      pages_with_schema: pipelineStep >= 6 ? 2 : null,
      structured_identity_coverage: pipelineStep >= 6 ? 0.4 : null,
      recommendations_total: pipelineStep >= 7 ? 1 : null,
      recommendations_high: pipelineStep >= 7 ? 1 : null,
      recommendations_medium: pipelineStep >= 7 ? 0 : null,
    },
    insights:
      pipelineStep >= 2
        ? [{ text: 'Improve metadata coverage on About.', source: 'SEO_FINDINGS' }]
        : [],
    recommendations:
      pipelineStep >= 7
        ? [
            {
              id: '55555555-5555-4555-8555-555555555555',
              title: 'Add meta descriptions',
              category: 'SEO',
              priority: 'HIGH',
              impact_score: 90,
              effort_score: 20,
            },
          ]
        : [],
    freshness: {
      last_website_crawl: auditCreated ? AUDIT.completed_at : null,
      last_seo_analysis: pipelineStep >= 2 ? AUDIT.completed_at : null,
      last_ai_analysis: pipelineStep >= 4 ? AUDIT.completed_at : null,
      last_recommendations_calculation: pipelineStep >= 7 ? AUDIT.completed_at : null,
    },
    brands: brandCreated ? [{ id: BRAND.id, name: BRAND.name }] : [],
    selection_rule: 'latest_completed',
  };
}

function explorerPayload() {
  return {
    audit: {
      id: AUDIT.id,
      brand_id: BRAND.id,
      brand_name: BRAND.name,
      created_at: AUDIT.created_at,
      completed_at: AUDIT.completed_at,
      status: AUDIT.status,
    },
    audits: [COMPLETED_AUDIT_OPTION],
    summary: {
      total_queries: 18,
      responses: 18,
      failed: 0,
      mention_rate: 0.5,
      citation_rate: 0.2,
    },
    items: [
      {
        query_id: '66666666-6666-4666-8666-666666666666',
        query_text: 'Who is Fixture Brand?',
        category: 'BRAND',
        created_at: AUDIT.created_at,
        has_response: true,
        response: {
          text: 'Fixture Brand makes outdoor equipment.',
          provider: 'mock',
          model: 'mock-model',
          brand_mentioned: true,
          brand_position: 1,
          citation_found: false,
          semantic_alignment: 0.8,
          latency_ms: 12,
        },
      },
    ],
    pagination: { page: 1, page_size: 20, total: 1, pages: 1 },
  };
}

async function json(route: Route, status: number, body: unknown): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

/** Authenticated workspace mocks used by smoke/responsive/a11y suites. */
export async function mockAuthenticatedWorkspace(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname.replace(/^\/api\/v1/, '') || '/';

    if (path === '/auth/me' && method === 'GET') {
      return json(route, 200, USER);
    }
    if (path === '/auth/logout' && method === 'POST') {
      return json(route, 200, { status: 'ok' });
    }
    if (path === '/dashboard/overview' && method === 'GET') {
      return json(route, 200, dashboardOverview({}));
    }
    if (path === '/brands' && method === 'GET') {
      return json(route, 200, { items: [BRAND], total: 1 });
    }
    if (path === `/brands/${BRAND.id}` && method === 'GET') {
      return json(route, 200, BRAND);
    }
    if (path === `/brands/${BRAND.id}/audits` && method === 'GET') {
      return json(route, 200, { items: [AUDIT], total: 1 });
    }
    if (path === '/reports' && method === 'GET') {
      return json(route, 200, {
        items: [REPORT],
        total: 1,
        page: 1,
        page_size: 20,
        completed_audits: [COMPLETED_AUDIT_OPTION],
      });
    }
    if (path === '/query-explorer' && method === 'GET') {
      return json(route, 200, explorerPayload());
    }
    if (path === '/intelligence/audits' && method === 'GET') {
      return json(route, 200, {
        audits: [COMPLETED_AUDIT_OPTION],
        selected_audit_id: AUDIT.id,
      });
    }
    if (path === `/audits/${AUDIT.id}/ai-visibility` && method === 'GET') {
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'AVAILABLE',
        overall_score: 55,
        metrics: {
          mention_rate: 0.5,
          citation_rate: 0.25,
          average_position: 2,
          position_score: 70,
          semantic_alignment: 0.4,
          semantic_score: 40,
        },
        components: {},
        total_queries: 1,
        successful_responses: 1,
        failed_responses: 0,
        response_coverage: 1,
        note: null,
      });
    }
    if (path === `/audits/${AUDIT.id}/entity` && method === 'GET') {
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'AVAILABLE',
        overall_score: 60,
        metrics: { canonical_consistency: 1 },
        components: {
          presence: 80,
          consistency: 70,
          structured_identity: 40,
          ai_recognition: 50,
        },
        component_details: [],
        evidence: {
          analyzable_pages: 6,
          pages_with_brand_in_title: 4,
          pages_with_brand_in_meta: 3,
          pages_with_canonical: 6,
          pages_with_same_origin_canonical: 6,
          pages_with_schema: 2,
          pages_with_entity_schema: 1,
          successful_ai_responses: 1,
          responses_mentioning_brand: 1,
          average_mention_position: 2,
          brand_name: BRAND.name,
          normalized_brand_name: 'fixture brand',
          origin: 'https://fixture.test',
        },
        notes: [],
      });
    }
    if (path === `/audits/${AUDIT.id}/recommendations` && method === 'GET') {
      return json(route, 200, {
        items: [
          {
            id: '55555555-5555-4555-8555-555555555555',
            title: 'Add meta descriptions',
            description: 'About page is missing a meta description.',
            category: 'SEO',
            priority: 'HIGH',
            impact_score: 90,
            effort_score: 20,
          },
        ],
        total: 1,
      });
    }
    if (path === '/intelligence/ask' && method === 'POST') {
      return json(route, 200, {
        answer: 'The main SEO issue is a missing meta description on the About page.',
        audit_id: AUDIT.id,
        sources: [],
        empty: false,
        message: null,
        context: {
          brand_name: BRAND.name,
          audit_date: AUDIT.completed_at,
          overall_score: 72,
          overall_status: 'PROVISIONAL',
        },
      });
    }
    return json(route, 200, {});
  });
}

/** Full core-workflow mocks including mutations for brand/audit/report pipeline. */
export async function mockCoreWorkflow(page: Page): Promise<void> {
  let brandCreated = false;
  let auditCreated = false;
  let pipelineStep = 0;
  let reportReady = false;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname.replace(/^\/api\/v1/, '') || '/';

    if (path === '/auth/login' && method === 'POST') {
      return json(route, 200, USER);
    }
    if (path === '/auth/me' && method === 'GET') {
      return json(route, 200, USER);
    }
    if (path === '/auth/logout' && method === 'POST') {
      return json(route, 200, { status: 'ok' });
    }
    if (path === '/brands' && method === 'GET') {
      return json(route, 200, {
        items: brandCreated ? [BRAND] : [],
        total: brandCreated ? 1 : 0,
      });
    }
    if (path === '/brands' && method === 'POST') {
      brandCreated = true;
      return json(route, 201, BRAND);
    }
    if (path === `/brands/${BRAND.id}` && method === 'GET') {
      return json(route, 200, BRAND);
    }
    if (path === `/brands/${BRAND.id}/audits` && method === 'GET') {
      return json(route, 200, {
        items: auditCreated ? [AUDIT] : [],
        total: auditCreated ? 1 : 0,
      });
    }
    if (path === `/brands/${BRAND.id}/audits` && method === 'POST') {
      auditCreated = true;
      return json(route, 201, {
        ...AUDIT,
        status: 'PENDING',
        pages_crawled: 0,
        completed_at: null,
        overall_score: null,
        website_score: null,
        seo_score: null,
        ai_visibility_score: null,
        entity_score: null,
        semantic_score: null,
      });
    }
    if (path === `/audits/${AUDIT.id}` && method === 'GET') {
      return json(route, 200, AUDIT);
    }
    if (path === `/audits/${AUDIT.id}/crawl` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 1);
      auditCreated = true;
      return json(route, 200, { audit_id: AUDIT.id, status: 'COMPLETED', pages_crawled: 6 });
    }
    if (path === `/audits/${AUDIT.id}/analyze-seo` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 2);
      return json(route, 200, { audit_id: AUDIT.id, findings_count: 4, status: 'OK' });
    }
    if (path === `/audits/${AUDIT.id}/seo-findings` && method === 'GET') {
      return json(route, 200, {
        items: [
          {
            id: '77777777-7777-4777-8777-777777777777',
            audit_id: AUDIT.id,
            page_id: null,
            category: 'Metadata',
            severity: 'HIGH',
            title: 'Missing meta description',
            description: 'About page is missing a meta description.',
            recommendation: 'Add a meta description.',
            created_at: AUDIT.created_at,
            page: null,
          },
        ],
        total: 1,
      });
    }
    if (path === `/audits/${AUDIT.id}/calculate-score` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 3);
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'PROVISIONAL',
        website_health: { score: 80, status: 'AVAILABLE' },
        seo: { score: 64, status: 'AVAILABLE' },
        overall: { score: 72, status: 'PROVISIONAL' },
        components: [],
        findings_count: 4,
        affected_pages: 2,
        analyzable_pages: 5,
        ai_visibility: { score: null, status: 'UNAVAILABLE' },
        entity_strength: { score: null, status: 'UNAVAILABLE' },
        note: 'Overall score is provisional.',
      });
    }
    if (path === `/audits/${AUDIT.id}/score` && method === 'GET') {
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'PROVISIONAL',
        website_health: { score: 80, status: 'AVAILABLE' },
        seo: { score: 64, status: 'AVAILABLE' },
        overall: { score: 72, status: 'PROVISIONAL' },
        components: [],
        findings_count: 4,
        affected_pages: 2,
        analyzable_pages: 5,
        ai_visibility: { score: pipelineStep >= 5 ? 55 : null, status: pipelineStep >= 5 ? 'AVAILABLE' : 'UNAVAILABLE' },
        entity_strength: { score: pipelineStep >= 6 ? 60 : null, status: pipelineStep >= 6 ? 'AVAILABLE' : 'UNAVAILABLE' },
        note: null,
      });
    }
    if (path === `/audits/${AUDIT.id}/ai-queries/run` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 4);
      return json(route, 200, {
        audit_id: AUDIT.id,
        queries_generated: 18,
        responses_succeeded: 18,
        responses_failed: 0,
        status: 'OK',
      });
    }
    if (path === `/audits/${AUDIT.id}/ai-queries` && method === 'GET') {
      return json(route, 200, { items: [], total: 18 });
    }
    if (path === `/audits/${AUDIT.id}/calculate-ai-visibility` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 5);
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'AVAILABLE',
        overall_score: 55,
        metrics: {},
        components: {},
        component_details: [],
        total_queries: 18,
        successful_responses: 18,
        failed_responses: 0,
        response_coverage: 1,
        note: null,
      });
    }
    if (path === `/audits/${AUDIT.id}/ai-visibility` && method === 'GET') {
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'AVAILABLE',
        overall_score: 55,
        metrics: {},
        components: {},
        component_details: [],
        total_queries: 18,
        successful_responses: 18,
        failed_responses: 0,
        response_coverage: 1,
        note: null,
      });
    }
    if (path === `/audits/${AUDIT.id}/calculate-entity` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 6);
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'AVAILABLE',
        overall_score: 60,
        evidence: {},
        metrics: {},
        components: {},
        component_details: [],
        note: null,
      });
    }
    if (path === `/audits/${AUDIT.id}/entity` && method === 'GET') {
      return json(route, 200, {
        audit_id: AUDIT.id,
        status: 'AVAILABLE',
        overall_score: 60,
        evidence: {},
        metrics: {},
        components: {},
        component_details: [],
        note: null,
      });
    }
    if (path === `/audits/${AUDIT.id}/calculate-recommendations` && method === 'POST') {
      pipelineStep = Math.max(pipelineStep, 7);
      return json(route, 200, {
        audit_id: AUDIT.id,
        recommendations_generated: 3,
        high: 1,
        medium: 1,
        low: 1,
        status: 'OK',
      });
    }
    if (path === `/audits/${AUDIT.id}/recommendations` && method === 'GET') {
      return json(route, 200, {
        items: [
          {
            id: '55555555-5555-4555-8555-555555555555',
            title: 'Add meta descriptions',
            description: 'About page is missing a meta description.',
            category: 'SEO',
            priority: 'HIGH',
            impact_score: 90,
            effort_score: 20,
          },
        ],
        total: 1,
      });
    }
    if (path === '/dashboard/overview' && method === 'GET') {
      return json(
        route,
        200,
        dashboardOverview({ brandCreated, auditCreated, pipelineStep }),
      );
    }
    if (path === '/query-explorer' && method === 'GET') {
      return json(route, 200, explorerPayload());
    }
    if (path === '/intelligence/audits' && method === 'GET') {
      return json(route, 200, {
        audits: auditCreated ? [COMPLETED_AUDIT_OPTION] : [],
        selected_audit_id: auditCreated ? AUDIT.id : null,
      });
    }
    if (path === '/intelligence/ask' && method === 'POST') {
      return json(route, 200, {
        answer: 'Fixture Brand has solid home metadata and needs About page meta coverage. Missing meta description.',
        audit_id: AUDIT.id,
        sources: [
          {
            type: 'seo_finding',
            id: '77777777-7777-4777-8777-777777777777',
            label: 'Missing meta description',
          },
        ],
        empty: false,
        message: null,
        context: {
          brand_name: BRAND.name,
          audit_date: AUDIT.completed_at,
          overall_score: 72,
          overall_status: 'PROVISIONAL',
        },
      });
    }
    if (path === '/reports' && method === 'GET') {
      return json(route, 200, {
        items: reportReady ? [REPORT] : [],
        total: reportReady ? 1 : 0,
        page: 1,
        page_size: 20,
        completed_audits: auditCreated ? [COMPLETED_AUDIT_OPTION] : [],
      });
    }
    if (path === '/reports' && method === 'POST') {
      reportReady = true;
      return json(route, 201, REPORT);
    }
    if (path === `/reports/${REPORT.id}` && method === 'GET') {
      return json(route, 200, REPORT);
    }
    if (path === `/reports/${REPORT.id}/download` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        headers: {
          'content-disposition': 'attachment; filename="Fixture-Brand-audit-intelligence-report.pdf"',
        },
        body: PDF_BYTES,
      });
    }

    return json(route, 404, { detail: 'Not found.' });
  });
}

export async function loginViaUi(page: Page): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(USER.email);
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard');
}
