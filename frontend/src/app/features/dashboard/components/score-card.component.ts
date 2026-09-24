import { Component, computed, input } from '@angular/core';

import { BadgeComponent, BadgeTone } from '../../../shared/components/badge/badge.component';
import {
  DashboardScoreCard,
  DashboardScoreStatus,
  formatCoverage,
  formatDashboardScore,
  scoreStatusLabel,
} from '../dashboard.models';

@Component({
  selector: 'app-dashboard-score-card',
  imports: [BadgeComponent],
  template: `
    <article class="dash-score-card" [attr.data-status]="card().status">
      <header class="dash-score-card__head">
        <h3 class="dash-score-card__title">{{ title() }}</h3>
        <app-badge [tone]="badgeTone()">{{ statusLabel() }}</app-badge>
      </header>

      <div class="dash-score-card__body">
        <div
          class="score-ring"
          role="img"
          [attr.aria-label]="ariaLabel()"
          [style.--ring-progress]="ringProgress()"
          [class.score-ring--empty]="card().score === null"
        >
          <svg viewBox="0 0 36 36" aria-hidden="true">
            <circle class="score-ring__track" cx="18" cy="18" r="15.5" />
            <circle class="score-ring__value" cx="18" cy="18" r="15.5" />
          </svg>
          <span class="score-ring__label">{{ displayScore() }}</span>
        </div>

        <div class="dash-score-card__meta">
          <p class="dash-score-card__explanation">{{ card().explanation }}</p>
          @if (detail(); as detailText) {
            <p class="dash-score-card__detail">{{ detailText }}</p>
          }
          @if (auditDate()) {
            <p class="dash-score-card__date">Latest audit · {{ auditDate() }}</p>
          }
        </div>
      </div>
    </article>
  `,
})
export class DashboardScoreCardComponent {
  readonly title = input.required<string>();
  readonly card = input.required<DashboardScoreCard>();
  readonly formattedDate = input<string | null>(null);

  readonly statusLabel = computed(() => scoreStatusLabel(this.card().status));

  readonly displayScore = computed(() => formatDashboardScore(this.card().score));

  readonly ringProgress = computed(() => {
    const score = this.card().score;
    if (score === null) {
      return '0';
    }
    return String(Math.min(100, Math.max(0, score)));
  });

  readonly badgeTone = computed((): BadgeTone => {
    const status: DashboardScoreStatus = this.card().status;
    if (status === 'AVAILABLE') {
      return 'success';
    }
    if (status === 'PROVISIONAL') {
      return 'warning';
    }
    return 'neutral';
  });

  readonly detail = computed(() => {
    const card = this.card();
    if (card.response_coverage != null) {
      return `Response coverage ${formatCoverage(card.response_coverage)}`;
    }
    if (card.evidence_coverage != null) {
      return `Evidence coverage ${formatCoverage(card.evidence_coverage)}`;
    }
    return null;
  });

  readonly auditDate = computed(() => this.formattedDate());

  readonly ariaLabel = computed(() => {
    const score = this.card().score;
    if (score === null) {
      return `${this.title()}: not calculated yet`;
    }
    return `${this.title()}: ${formatDashboardScore(score)} out of 100, ${this.statusLabel()}`;
  });
}
