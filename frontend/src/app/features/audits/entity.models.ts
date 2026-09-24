export type EntityStatus = 'AVAILABLE' | 'UNAVAILABLE' | 'PROVISIONAL';

export interface EntityEvidence {
  analyzable_pages: number;
  pages_with_brand_in_title: number;
  pages_with_brand_in_meta: number;
  pages_with_canonical: number;
  pages_with_same_origin_canonical: number;
  pages_with_schema: number;
  pages_with_entity_schema: number;
  successful_ai_responses: number;
  responses_mentioning_brand: number;
  average_mention_position: number | null;
  brand_name: string;
  normalized_brand_name: string;
  origin: string | null;
}

export interface EntityMetrics {
  title_presence_rate: number | null;
  meta_presence_rate: number | null;
  title_consistency: number | null;
  canonical_consistency: number | null;
  schema_consistency: number | null;
  entity_schema_coverage: number | null;
  schema_quality: number | null;
  ai_mention_rate: number | null;
  ai_position_score: number | null;
}

export interface EntityComponentDetail {
  name: string;
  score: number | null;
  status: EntityStatus;
  weight: number;
  effective_weight: number | null;
  sample_size: number;
}

export interface EntityComponentsSummary {
  presence: number | null;
  consistency: number | null;
  structured_identity: number | null;
  ai_recognition: number | null;
}

export interface EntityStrengthResponse {
  audit_id: string;
  status: EntityStatus;
  overall_score: number | null;
  metrics: EntityMetrics;
  components: EntityComponentsSummary;
  component_details: EntityComponentDetail[];
  evidence: EntityEvidence;
  notes: string[];
}

export function entityStatusLabel(status: EntityStatus | null | undefined): string {
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

export function entityStatusTone(
  status: EntityStatus | null | undefined,
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

export function entityComponentLabel(name: string): string {
  switch (name) {
    case 'presence':
      return 'Entity Presence';
    case 'consistency':
      return 'Entity Consistency';
    case 'structured_identity':
      return 'Structured Identity';
    case 'ai_recognition':
      return 'AI Entity Recognition';
    default:
      return name;
  }
}

export function formatEntityValue(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return Number(value).toFixed(digits);
}
