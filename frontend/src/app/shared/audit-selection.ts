import { IntelligenceAudit, IntelligenceAuditList } from '../features/intelligence-chat/intelligence.models';

/** Uses the catalog's selected_audit_id. Does not choose an audit itself. */
export function selectedOwnedAudit(
  catalog: IntelligenceAuditList,
  requestedId: string,
): IntelligenceAudit | null {
  if (requestedId) {
    return catalog.audits.find((audit) => audit.id === requestedId) ?? null;
  }
  if (!catalog.selected_audit_id) {
    return null;
  }
  return catalog.audits.find((audit) => audit.id === catalog.selected_audit_id) ?? null;
}
