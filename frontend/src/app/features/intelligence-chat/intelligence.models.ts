import { formatDisplayDate } from '../../shared/format';

export type AuditStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface IntelligenceAudit {
  id: string;
  brand_id: string;
  brand_name: string;
  status: AuditStatus;
  created_at: string | null;
  completed_at: string | null;
}

export interface IntelligenceAuditList {
  audits: IntelligenceAudit[];
  selected_audit_id: string | null;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AskRequest {
  audit_id: string;
  question: string;
  history: HistoryMessage[];
}

export interface EvidenceSource {
  type: string;
  id: string;
  label: string;
}

export interface AskContext {
  brand_name: string;
  audit_date: string | null;
  overall_score: number | null;
  overall_status: string;
}

export interface AskResponse {
  audit_id: string | null;
  answer: string | null;
  context: AskContext | null;
  sources: EvidenceSource[];
  empty: boolean;
  message: string | null;
}

export type ChatRole = 'user' | 'assistant';
export type ChatStatus = 'complete' | 'pending' | 'error';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  status: ChatStatus;
  sources?: EvidenceSource[];
  retryQuestion?: string;
}

export const SUGGESTED_QUESTIONS = [
  'Why is my overall score provisional?',
  'What are my biggest SEO issues?',
  'Why is my AI visibility score low?',
  "Which AI queries don't mention my brand?",
  'What should I fix first?',
  'How strong is my entity presence?',
] as const;

export const QUESTION_MAX_LENGTH = 2000;

export function formatAuditDate(value: string | null | undefined): string | null {
  return formatDisplayDate(value);
}

export function auditOptionLabel(audit: IntelligenceAudit): string {
  const date = formatAuditDate(audit.completed_at ?? audit.created_at);
  return date ? `${audit.brand_name} — ${date}` : audit.brand_name;
}

export function evidenceTypeLabel(type: string): string {
  switch (type) {
    case 'seo_finding':
      return 'SEO Finding';
    case 'recommendation':
      return 'Recommendation';
    case 'ai_query':
      return 'AI Query';
    case 'ai_response':
      return 'AI Response';
    case 'website_page':
      return 'Website Page';
    case 'audit_score':
      return 'Audit Score';
    case 'ai_visibility_metric':
      return 'AI Visibility';
    case 'entity_metric':
      return 'Entity';
    default:
      return 'Evidence';
  }
}
