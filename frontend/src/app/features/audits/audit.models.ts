export type AuditStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export type FindingSeverity = 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type ScoreStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'PROVISIONAL';

export interface AuditSummary {
  id: string;
  brand_id: string;
  status: AuditStatus;
  pages_crawled: number;
  overall_score: number | null;
  website_score: number | null;
  seo_score: number | null;
  ai_visibility_score: number | null;
  entity_score: number | null;
  semantic_score: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface AuditListResponse {
  items: AuditSummary[];
}

export interface CrawlResponse {
  audit_id: string;
  status: AuditStatus;
  pages_crawled: number;
}

export interface SeoAnalyzeResponse {
  audit_id: string;
  findings_count: number;
  status: string;
}

export interface SeoFindingPageInfo {
  id: string;
  url: string;
  status_code: number | null;
}

export interface SeoFinding {
  id: string;
  audit_id: string;
  page_id: string | null;
  category: string;
  severity: FindingSeverity;
  title: string;
  description: string | null;
  recommendation: string | null;
  created_at: string;
  page: SeoFindingPageInfo | null;
}

export interface SeoFindingListResponse {
  items: SeoFinding[];
  total: number;
}

export interface ScoreValue {
  score: number | null;
  status: ScoreStatus;
}

export interface ComponentScoreSummary {
  name: string;
  score: number | null;
  status: ScoreStatus;
  findings_count: number;
  affected_pages: number;
  top_penalty_categories: string[];
}

export interface AuditScoreResponse {
  audit_id: string;
  status: ScoreStatus;
  website_health: ScoreValue;
  seo: ScoreValue;
  overall: ScoreValue;
  components: ComponentScoreSummary[];
  findings_count: number;
  affected_pages: number;
  analyzable_pages: number;
  ai_visibility: ScoreValue;
  entity_strength: ScoreValue;
  note: string | null;
}

/** Short status for history lists. Crawl-progress copy stays in auditStatusLabel. */
export function auditHistoryStatusLabel(status: AuditStatus): string {
  switch (status) {
    case 'PENDING':
      return 'Pending';
    case 'RUNNING':
      return 'Running';
    case 'COMPLETED':
      return 'Completed';
    case 'FAILED':
      return 'Failed';
  }
}

export function auditHistoryStatusTone(
  status: AuditStatus,
): 'success' | 'info' | 'warning' | 'danger' {
  switch (status) {
    case 'COMPLETED':
      return 'success';
    case 'RUNNING':
      return 'info';
    case 'FAILED':
      return 'danger';
    case 'PENDING':
      return 'warning';
  }
}

/**
 * Availability of the stored overall score.
 * Null is unavailable. A stored overall is provisional when AI Visibility or
 * Entity Strength has not been stored, matching the dashboard's persisted-column rule.
 */
export function overallScoreAvailability(
  audit: Pick<AuditSummary, 'overall_score' | 'ai_visibility_score' | 'entity_score'>,
): ScoreStatus {
  if (audit.overall_score === null || audit.overall_score === undefined) {
    return 'UNAVAILABLE';
  }
  if (audit.ai_visibility_score === null || audit.entity_score === null) {
    return 'PROVISIONAL';
  }
  return 'AVAILABLE';
}

export function auditStatusLabel(status: AuditStatus | null): string {
  switch (status) {
    case 'PENDING':
      return 'Audit pending';
    case 'RUNNING':
      return 'Crawling website…';
    case 'COMPLETED':
      return 'Website crawl completed';
    case 'FAILED':
      return 'Crawl failed';
    default:
      return 'No audits yet';
  }
}

export function crawlCompletedMessage(pages: number): string {
  const noun = pages === 1 ? 'page' : 'pages';
  return `Website crawl completed — ${pages} ${noun} crawled.`;
}

export function seoAnalysisCompletedMessage(count: number): string {
  const noun = count === 1 ? 'finding' : 'findings';
  return `SEO analysis completed — ${count} ${noun}.`;
}

export function severityLabel(severity: FindingSeverity): string {
  switch (severity) {
    case 'HIGH':
      return 'High';
    case 'MEDIUM':
      return 'Medium';
    case 'LOW':
      return 'Low';
    case 'INFO':
      return 'Info';
  }
}

export function severityBadgeTone(severity: FindingSeverity): 'danger' | 'warning' | 'neutral' | 'info' {
  switch (severity) {
    case 'HIGH':
      return 'danger';
    case 'MEDIUM':
      return 'warning';
    case 'LOW':
      return 'info';
    case 'INFO':
      return 'info';
  }
}

export function truncateUrl(url: string, max = 64): string {
  if (url.length <= max) {
    return url;
  }
  return `${url.slice(0, max - 1)}…`;
}

export function componentLabel(name: string): string {
  switch (name) {
    case 'technical':
      return 'Technical';
    case 'seo':
      return 'SEO';
    case 'content':
      return 'Content';
    case 'structured_data':
      return 'Structured Data';
    default:
      return name;
  }
}

export function scoreImpactSummary(findings: number, pages: number): string {
  const findingNoun = findings === 1 ? 'finding' : 'findings';
  const pageNoun = pages === 1 ? 'page' : 'pages';
  return `${findings} ${findingNoun} across ${pages} ${pageNoun}`;
}
