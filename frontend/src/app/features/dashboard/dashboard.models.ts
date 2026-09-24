import { formatCount, formatMetricScore, formatPercent } from '../../shared/format';

export type AuditStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export type DashboardScoreStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'PROVISIONAL';

export type DashboardInsightSource =
  | 'SEO_FINDINGS'
  | 'AI_VISIBILITY'
  | 'ENTITY'
  | 'RECOMMENDATIONS'
  | 'WEBSITE';

export type RecommendationPriority = 'HIGH' | 'MEDIUM' | 'LOW';

export interface DashboardWorkspace {
  brand_count: number;
  audit_count: number;
  completed_audit_count: number;
}

export interface DashboardSelectedAudit {
  id: string;
  brand_id: string;
  brand_name: string;
  status: AuditStatus;
  created_at: string;
  completed_at: string | null;
  website_score_available: boolean;
  seo_score_available: boolean;
  ai_visibility_available: boolean;
  entity_available: boolean;
  overall_score_available: boolean;
  pages_crawled: number;
  seo_findings: number;
}

export interface DashboardScoreCard {
  score: number | null;
  status: DashboardScoreStatus;
  explanation: string;
  audit_date?: string | null;
  response_coverage?: number | null;
  evidence_coverage?: number | null;
}

export interface DashboardOverallScore {
  score: number | null;
  status: DashboardScoreStatus;
  explanation: string;
}

export interface DashboardScores {
  overall: DashboardOverallScore;
  website: DashboardScoreCard;
  seo: DashboardScoreCard;
  ai_visibility: DashboardScoreCard;
  entity: DashboardScoreCard;
}

export interface DashboardSnapshot {
  pages_crawled: number | null;
  seo_findings: number | null;
  high_severity_findings: number | null;
  ai_queries: number | null;
  ai_successful_responses: number | null;
  ai_response_coverage: number | null;
  ai_mention_rate: number | null;
  entity_pages_analyzed: number | null;
  pages_with_schema: number | null;
  structured_identity_coverage: number | null;
  recommendations_total: number | null;
  recommendations_high: number | null;
  recommendations_medium: number | null;
}

export interface DashboardInsight {
  text: string;
  source: DashboardInsightSource;
}

export interface DashboardRecommendationPreview {
  id: string;
  title: string;
  category: string;
  priority: RecommendationPriority;
  impact_score: number | null;
  effort_score: number | null;
}

export interface DashboardFreshness {
  last_website_crawl: string | null;
  last_seo_analysis: string | null;
  last_ai_analysis: string | null;
  last_recommendations_calculation: string | null;
}

export interface DashboardBrandOption {
  id: string;
  name: string;
}

export interface DashboardOverview {
  workspace: DashboardWorkspace;
  selected_audit: DashboardSelectedAudit | null;
  scores: DashboardScores;
  snapshot: DashboardSnapshot;
  insights: DashboardInsight[];
  recommendations: DashboardRecommendationPreview[];
  freshness: DashboardFreshness;
  brands: DashboardBrandOption[];
  selection_rule: string;
}

const STATUS_LABELS: Record<AuditStatus, string> = {
  PENDING: 'Pending',
  RUNNING: 'Running',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
};

const SCORE_STATUS_LABELS: Record<DashboardScoreStatus, string> = {
  AVAILABLE: 'Available',
  UNAVAILABLE: 'Not calculated yet',
  PROVISIONAL: 'Provisional',
};

export function auditStatusLabel(status: AuditStatus): string {
  return STATUS_LABELS[status];
}

export function scoreStatusLabel(status: DashboardScoreStatus): string {
  return SCORE_STATUS_LABELS[status];
}

export function formatDashboardScore(value: number | null): string {
  return formatMetricScore(value, 1);
}

export function formatCoverage(value: number | null | undefined): string {
  return formatPercent(value, 1);
}

export function formatMetric(value: number | null | undefined): string {
  return formatCount(value);
}
