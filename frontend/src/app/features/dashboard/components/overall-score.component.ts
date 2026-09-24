import { Component, computed, input } from '@angular/core';

import { BadgeComponent, BadgeTone } from '../../../shared/components/badge/badge.component';
import {
  DashboardOverallScore,
  formatDashboardScore,
  scoreStatusLabel,
} from '../dashboard.models';

@Component({
  selector: 'app-dashboard-overall-score',
  imports: [BadgeComponent],
  template: `
    <article class="dash-overall" [attr.data-status]="overall().status">
      <div class="dash-overall__copy">
        <p class="dash-overall__eyebrow">Overall Intelligence</p>
        <div class="dash-overall__score-row">
          <p class="dash-overall__score" aria-live="polite">{{ displayScore() }}</p>
          <app-badge [tone]="badgeTone()">{{ statusLabel() }}</app-badge>
        </div>
        <p class="dash-overall__explanation">{{ overall().explanation }}</p>
      </div>
      <div
        class="score-ring score-ring--large"
        role="img"
        [attr.aria-label]="ariaLabel()"
        [style.--ring-progress]="ringProgress()"
        [class.score-ring--empty]="overall().score === null"
      >
        <svg viewBox="0 0 36 36" aria-hidden="true">
          <circle class="score-ring__track" cx="18" cy="18" r="15.5" />
          <circle class="score-ring__value" cx="18" cy="18" r="15.5" />
        </svg>
        <span class="score-ring__label">{{ displayScore() }}</span>
      </div>
    </article>
  `,
})
export class DashboardOverallScoreComponent {
  readonly overall = input.required<DashboardOverallScore>();

  readonly displayScore = computed(() => formatDashboardScore(this.overall().score));

  readonly statusLabel = computed(() => {
    if (this.overall().status === 'PROVISIONAL') {
      return 'Provisional';
    }
    if (this.overall().status === 'UNAVAILABLE') {
      return 'Not available';
    }
    return scoreStatusLabel(this.overall().status);
  });

  readonly badgeTone = computed((): BadgeTone => {
    const status = this.overall().status;
    if (status === 'AVAILABLE') {
      return 'success';
    }
    if (status === 'PROVISIONAL') {
      return 'warning';
    }
    return 'neutral';
  });

  readonly ringProgress = computed(() => {
    const score = this.overall().score;
    if (score === null) {
      return '0';
    }
    return String(Math.min(100, Math.max(0, score)));
  });

  readonly ariaLabel = computed(() => {
    const score = this.overall().score;
    if (score === null) {
      return 'Overall intelligence not available';
    }
    return `Overall intelligence ${formatDashboardScore(score)}, ${this.statusLabel()}`;
  });
}
