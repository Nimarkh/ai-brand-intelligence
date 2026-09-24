import { Component, input } from '@angular/core';

import { formatMetric } from '../dashboard.models';

@Component({
  selector: 'app-dashboard-metric-row',
  template: `
    <div class="dash-metric-row">
      <span class="dash-metric-row__label">{{ label() }}</span>
      <span class="dash-metric-row__value">{{ display() }}</span>
    </div>
  `,
})
export class DashboardMetricRowComponent {
  readonly label = input.required<string>();
  readonly value = input<number | null | undefined>(null);

  display(): string {
    return formatMetric(this.value());
  }
}
