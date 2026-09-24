import { formatCount, formatDisplayDate, formatDisplayDateTime, formatMilliseconds } from '../../shared/format';

export type QueryCategory =
  | 'BRAND'
  | 'PRODUCT'
  | 'INDUSTRY'
  | 'COMPETITOR'
  | 'COMMERCIAL'
  | 'INFORMATIONAL';

export type AuditStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface QueryExplorerAudit {
  id: string;
  brand_id: string;
  brand_name: string;
  created_at: string;
  completed_at: string | null;
  status: AuditStatus;
}

export interface QueryExplorerSummary {
  total_queries: number;
  responses: number;
  failed: number;
  mention_rate: number | null;
  citation_rate: number | null;
}

export interface QueryExplorerResponseBody {
  text: string;
  provider: string;
  model: string;
  brand_mentioned: boolean | null;
  brand_position: number | null;
  citation_found: boolean | null;
  semantic_alignment: number | null;
  latency_ms: number | null;
}

export interface QueryExplorerItem {
  query_id: string;
  query_text: string;
  category: QueryCategory;
  created_at: string;
  has_response: boolean;
  response: QueryExplorerResponseBody | null;
}

export interface QueryExplorerPagination {
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface QueryExplorerView {
  audit: QueryExplorerAudit | null;
  audits: QueryExplorerAudit[];
  summary: QueryExplorerSummary | null;
  items: QueryExplorerItem[];
  pagination: QueryExplorerPagination;
}

export interface QueryExplorerParams {
  auditId?: string | null;
  category?: QueryCategory | null;
  search?: string | null;
  hasResponse?: boolean | null;
  brandMentioned?: boolean | null;
  citationFound?: boolean | null;
  page?: number;
  pageSize?: number;
}

export const UNAVAILABLE = '—';

export const QUERY_CATEGORIES: readonly QueryCategory[] = [
  'BRAND',
  'PRODUCT',
  'INDUSTRY',
  'COMPETITOR',
  'COMMERCIAL',
  'INFORMATIONAL',
];

const CATEGORY_LABELS: Record<QueryCategory, string> = {
  BRAND: 'Brand',
  PRODUCT: 'Product',
  INDUSTRY: 'Industry',
  COMPETITOR: 'Competitor',
  COMMERCIAL: 'Commercial',
  INFORMATIONAL: 'Informational',
};

export function categoryLabel(category: QueryCategory): string {
  return CATEGORY_LABELS[category];
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatAuditDate(value: string | null | undefined): string | null {
  return formatDisplayDate(value);
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return UNAVAILABLE;
  }
  return formatDisplayDateTime(value) ?? UNAVAILABLE;
}

export function yesNo(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return UNAVAILABLE;
  }
  return value ? 'Yes' : 'No';
}

export function formatAlignment(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatLatency(value: number | null | undefined): string {
  return formatMilliseconds(value);
}

export function formatPosition(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return UNAVAILABLE;
  }
  return String(value);
}
