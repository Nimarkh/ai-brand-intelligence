export type AiQueryCategory =
  | 'BRAND'
  | 'PRODUCT'
  | 'INDUSTRY'
  | 'COMPETITOR'
  | 'COMMERCIAL'
  | 'INFORMATIONAL';

export interface AiQueryRunResponse {
  audit_id: string;
  queries_generated: number;
  responses_succeeded: number;
  responses_failed: number;
  status: string;
}

export interface AiQueryListItem {
  id: string;
  query_text: string;
  category: AiQueryCategory;
  created_at: string;
  has_response: boolean;
}

export interface AiQueryListResponse {
  items: AiQueryListItem[];
  total: number;
}

export interface AiQueryResponseDetail {
  id: string;
  provider: string;
  model: string;
  response_text: string;
  brand_mentioned: boolean | null;
  brand_position: number | null;
  citation_found: boolean | null;
  semantic_alignment: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface AiQueryDetail {
  id: string;
  audit_id: string;
  query_text: string;
  category: AiQueryCategory;
  created_at: string;
  response: AiQueryResponseDetail | null;
}

export function aiQueryRunSummary(result: AiQueryRunResponse): string {
  const failedNote =
    result.responses_failed > 0
      ? ` (${result.responses_failed} failed)`
      : '';
  return `AI query analysis completed — ${result.queries_generated} queries, ${result.responses_succeeded} responses${failedNote}.`;
}

export function formatSemanticAlignment(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : String(value);
}
