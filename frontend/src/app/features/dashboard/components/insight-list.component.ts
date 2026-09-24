import { Component, input } from '@angular/core';

import { DashboardInsight } from '../dashboard.models';

@Component({
  selector: 'app-dashboard-insight-list',
  template: `
    <ul class="dash-insights">
      @for (insight of insights(); track insight.text + insight.source) {
        <li class="dash-insights__item">
          <span class="dash-insights__source">{{ sourceLabel(insight.source) }}</span>
          <p class="dash-insights__text">{{ insight.text }}</p>
        </li>
      }
    </ul>
  `,
})
export class DashboardInsightListComponent {
  readonly insights = input.required<DashboardInsight[]>();

  sourceLabel(source: DashboardInsight['source']): string {
    switch (source) {
      case 'SEO_FINDINGS':
        return 'SEO';
      case 'AI_VISIBILITY':
        return 'AI';
      case 'ENTITY':
        return 'Entity';
      case 'RECOMMENDATIONS':
        return 'Recommendations';
      case 'WEBSITE':
        return 'Website';
      default:
        return source;
    }
  }
}
