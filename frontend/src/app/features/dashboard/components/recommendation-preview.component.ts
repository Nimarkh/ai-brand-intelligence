import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { BadgeComponent } from '../../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../../shared/components/empty-state/empty-state.component';
import {
  categoryLabel,
  formatScoreValue,
  priorityLabel,
  priorityTone,
} from '../../audits/recommendation.models';
import {
  DashboardRecommendationPreview,
  RecommendationPriority,
} from '../dashboard.models';

@Component({
  selector: 'app-dashboard-recommendation-preview',
  imports: [RouterLink, BadgeComponent, ButtonComponent, EmptyStateComponent],
  template: `
    @if (recommendations().length === 0) {
      <app-empty-state
        icon="recommendations"
        title="No recommendations yet."
        description="Run recommendation calculation on an audit to see prioritized next steps here."
        [compact]="true"
        [headingLevel]="3"
      />
    } @else {
      <ul class="dash-recs">
        @for (item of recommendations(); track item.id) {
          <li class="dash-recs__item">
            <div class="dash-recs__main">
              <p class="dash-recs__title">{{ item.title }}</p>
              <div class="dash-recs__meta">
                <app-badge [tone]="tone(item.priority)">{{ label(item.priority) }}</app-badge>
                <span>{{ category(item.category) }}</span>
                <span>Impact {{ formatScore(item.impact_score) }}</span>
                <span>Effort {{ formatScore(item.effort_score) }}</span>
              </div>
            </div>
          </li>
        }
      </ul>
      @if (auditId()) {
        <div class="dash-recs__footer">
          <a appButton variant="secondary" [routerLink]="['/audits', auditId()]">
            View all recommendations
          </a>
        </div>
      }
    }
  `,
})
export class DashboardRecommendationPreviewComponent {
  readonly recommendations = input.required<DashboardRecommendationPreview[]>();
  readonly auditId = input<string | null>(null);

  formatScore(value: number | null): string {
    return formatScoreValue(value);
  }

  label(priority: RecommendationPriority): string {
    return priorityLabel(priority);
  }

  tone(priority: RecommendationPriority) {
    return priorityTone(priority);
  }

  category(value: string): string {
    return categoryLabel(value);
  }
}
