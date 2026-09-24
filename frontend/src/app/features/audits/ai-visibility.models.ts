export type VisibilityStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'PROVISIONAL';

export interface VisibilityMetrics {
  mention_rate: number | null;
  citation_rate: number | null;
  average_position: number | null;
  position_score: number | null;
  semantic_alignment: number | null;
  semantic_score: number | null;
}

export interface VisibilityComponents {
  mention: number | null;
  citation: number | null;
  position: number | null;
  semantic: number | null;
}

export interface AIVisibilityResponse {
  audit_id: string;
  status: VisibilityStatus;
  overall_score: number | null;
  metrics: VisibilityMetrics;
  components: VisibilityComponents;
  total_queries: number;
  successful_responses: number;
  failed_responses: number;
  response_coverage: number | null;
  note: string | null;
}

export function visibilityStatusLabel(status: VisibilityStatus | null | undefined): string {
  switch (status) {
    case 'AVAILABLE':
      return 'Available';
    case 'PROVISIONAL':
      return 'Provisional';
    case 'UNAVAILABLE':
    default:
      return 'Not available';
  }
}

export function visibilityStatusTone(
  status: VisibilityStatus | null | undefined,
): 'info' | 'warning' | 'neutral' {
  switch (status) {
    case 'AVAILABLE':
      return 'info';
    case 'PROVISIONAL':
      return 'warning';
    default:
      return 'neutral';
  }
}

export function formatVisibilityValue(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return value.toFixed(digits);
}

export function formatRateAsPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return `${(value * 100).toFixed(1)}%`;
}
