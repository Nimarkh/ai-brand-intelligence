import { Component, input, output } from '@angular/core';

import {
  IntelligenceAudit,
  auditOptionLabel,
} from '../../../features/intelligence-chat/intelligence.models';

@Component({
  selector: 'app-audit-select',
  template: `
    @if (audits().length > 1) {
      <label class="intel-audit">
        <span class="intel-audit__label" [id]="labelId()">Audit</span>
        <select
          class="intel-audit__select"
          [attr.aria-labelledby]="labelId()"
          [value]="selectedId() ?? ''"
          (change)="changed.emit(selectValue($event))"
        >
          @for (audit of audits(); track audit.id) {
            <option [value]="audit.id">{{ optionLabel(audit) }}</option>
          }
        </select>
      </label>
    }
  `,
})
export class AuditSelectComponent {
  readonly audits = input.required<IntelligenceAudit[]>();
  readonly selectedId = input<string | null>(null);
  readonly labelId = input('owned-audit-label');
  readonly changed = output<string>();

  optionLabel(audit: IntelligenceAudit): string {
    return auditOptionLabel(audit);
  }

  selectValue(event: Event): string {
    return (event.target as HTMLSelectElement).value;
  }
}
