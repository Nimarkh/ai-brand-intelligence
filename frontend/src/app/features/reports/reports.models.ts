import { formatDateOrDash, formatScoreOutOf100 } from '../../shared/format';

export type ReportStatus = 'GENERATING' | 'READY' | 'FAILED';

export interface ScoreView {
  key: string;
  label: string;
  score: number | null;
  status: string;
}

export interface ReportListItem {
  id: string;
  audit_id: string;
  brand_name: string;
  title: string;
  status: ReportStatus;
  created_at: string;
  completed_at: string | null;
  audit_date: string | null;
}

export interface CompletedAuditOption {
  id: string;
  brand_name: string;
  created_at: string;
  completed_at: string | null;
}

export interface ReportList {
  items: ReportListItem[];
  total: number;
  page: number;
  page_size: number;
  completed_audits: CompletedAuditOption[];
}

export interface ReportDetail {
  id: string;
  audit_id: string;
  brand_name: string;
  website: string | null;
  title: string;
  status: ReportStatus;
  created_at: string;
  completed_at: string | null;
  audit_date: string | null;
  generated_at: string | null;
  overall_score: number | null;
  overall_status: string;
  overall_note: string | null;
  scores: ScoreView[];
  sections: string[];
  message: string | null;
}

export function formatReportDate(value: string | null | undefined): string {
  return formatDateOrDash(value);
}

export function formatScore(value: number | null | undefined): string {
  return formatScoreOutOf100(value);
}

export function statusLabel(status: ReportStatus): string {
  if (status === 'GENERATING') {
    return 'Generating…';
  }
  if (status === 'READY') {
    return 'Ready';
  }
  return 'Failed';
}

export function statusTone(status: ReportStatus): 'success' | 'danger' | 'info' {
  if (status === 'READY') {
    return 'success';
  }
  if (status === 'FAILED') {
    return 'danger';
  }
  return 'info';
}

export function auditOptionLabel(audit: CompletedAuditOption): string {
  return `${audit.brand_name} — ${formatReportDate(audit.completed_at ?? audit.created_at)}`;
}
