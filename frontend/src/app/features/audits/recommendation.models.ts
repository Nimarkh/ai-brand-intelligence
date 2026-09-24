export type RecommendationPriority = 'HIGH' | 'MEDIUM' | 'LOW';

export type RecommendationCategory =
  | 'TECHNICAL'
  | 'SEO'
  | 'CONTENT'
  | 'STRUCTURED_DATA'
  | 'AI_VISIBILITY'
  | 'ENTITY'
  | 'PERFORMANCE';

export interface RecommendationItem {
  id: string;
  title: string;
  description: string | null;
  category: string;
  priority: RecommendationPriority;
  impact_score: number | null;
  effort_score: number | null;
}

export interface RecommendationListResponse {
  items: RecommendationItem[];
  total: number;
}

export interface RecommendationRunResponse {
  audit_id: string;
  recommendations_generated: number;
  high: number;
  medium: number;
  low: number;
  status: string;
}

export function priorityLabel(priority: RecommendationPriority | null | undefined): string {
  switch (priority) {
    case 'HIGH':
      return 'High priority';
    case 'MEDIUM':
      return 'Medium priority';
    case 'LOW':
      return 'Low priority';
    default:
      return 'Priority';
  }
}

export function priorityTone(
  priority: RecommendationPriority | null | undefined,
): 'danger' | 'warning' | 'info' | 'neutral' {
  switch (priority) {
    case 'HIGH':
      return 'danger';
    case 'MEDIUM':
      return 'warning';
    case 'LOW':
      return 'info';
    default:
      return 'neutral';
  }
}

export function categoryLabel(category: string | null | undefined): string {
  switch (category) {
    case 'TECHNICAL':
      return 'Technical';
    case 'SEO':
      return 'SEO';
    case 'CONTENT':
      return 'Content';
    case 'STRUCTURED_DATA':
      return 'Structured data';
    case 'AI_VISIBILITY':
      return 'AI Visibility';
    case 'ENTITY':
      return 'Entity Intelligence';
    case 'PERFORMANCE':
      return 'Performance';
    default:
      return category || 'Recommendation';
  }
}

export function formatScoreValue(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return Number(value).toFixed(digits);
}
